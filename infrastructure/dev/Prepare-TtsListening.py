"""Audit existing synthetic WAVs and build a static, loopback-only listening pack.

No synthesis, engine initialization, downloads or active configuration changes.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import html
import json
import math
import shutil
import sys
import urllib.request
import wave
from collections import Counter
from pathlib import Path

ENGINES = ("chatterbox", "moss")
CASES = ("short", "two", "list")
# Predeclared, counterbalanced order; independent of sample metrics/content.
ORDER = {"short": ENGINES, "two": tuple(reversed(ENGINES)), "list": ENGINES}
CONFIG = {
    "chatterbox": {
        "engine": "Chatterbox multilingual 0.1.7",
        "device": "CUDA / RTX 2070",
        "language": "de",
        "voiceId": "velora",
        "cfgWeight": 0.5,
        "temperature": 0.65,
        "repetitionPenalty": 2.0,
        "exaggeration": 0.45,
        "seed": "not fixed by resident service",
    },
    "moss": {
        "engine": "MOSS-TTS-Nano 100M ONNX",
        "revision": "cc7bdf19c7639c0870dab22045a33b442760f6be",
        "device": "CPUExecutionProvider / two threads",
        "sampleMode": "fixed",
        "doSample": True,
        "streaming": "internal codec decoding; complete WAV delivery",
        "maxNewFrames": 375,
        "voiceCloneMaxTextTokens": 75,
        "enableWetext": True,
        "enableNormalizeTtsText": True,
        "seed": "82000 + iteration",
    },
}
REFERENCE_SHA = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"


def inspect_wav(path: Path, expected_sha: str) -> dict:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise ValueError("WAV_SHA256_MISMATCH")
    with wave.open(str(path)) as audio:
        channels, width, rate, count = (
            audio.getnchannels(),
            audio.getsampwidth(),
            audio.getframerate(),
            audio.getnframes(),
        )
        raw = audio.readframes(count)
    if width != 2 or not count or len(raw) != count * channels * width:
        raise ValueError("INVALID_OR_TRUNCATED_PCM16")
    samples = array.array("h", raw)
    if sys.byteorder != "little":
        samples.byteswap()
    # 20ms RMS windows across all channels, no destructive stereo downmix.
    window = max(1, round(rate * 0.02)) * channels
    quiet = []
    exact_blocks = Counter()
    for offset in range(0, len(samples), window):
        block = samples[offset : offset + window]
        rms = math.sqrt(sum(value * value for value in block) / len(block)) / 32768
        quiet.append(rms < 0.01)  # -40dBFS; energy heuristic, not a VAD.
        if rms >= 0.01 and len(block) == window:
            exact_blocks[hashlib.sha256(block.tobytes()).digest()] += 1
    leading = next((i for i, value in enumerate(quiet) if not value), len(quiet))
    trailing = next(
        (i for i, value in enumerate(reversed(quiet)) if not value), len(quiet)
    )
    longest = current = 0
    for value in quiet:
        current = current + 1 if value else 0
        longest = max(longest, current)
    duration = count / rate
    return {
        "sha256": actual,
        "audioSeconds": duration,
        "sampleRate": rate,
        "channels": channels,
        "sampleWidth": width,
        "quietThresholdDbfs": -40,
        "windowMs": 20,
        "quietSeconds": min(duration, sum(quiet) * 0.02),
        "leadingQuietSeconds": min(duration, leading * 0.02),
        "trailingQuietSeconds": min(duration, trailing * 0.02),
        "longestQuietSeconds": min(duration, longest * 0.02),
        "exactRepeatedNonquiet20msBlocks": sum(n - 1 for n in exact_blocks.values()),
        "note": "Energy and exact-PCM heuristics do not establish intelligibility, semantic repetition or completeness.",
    }


def transcribe(path: Path) -> dict:
    # Fixed local endpoint only. No model hint/prompt containing the expected text.
    boundary = "kyrion-synthetic-listening-audit"
    data = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nde\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="response_format"\r\n\r\njson\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        "http://127.0.0.1:8040/v1/audio/transcriptions",
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    # Ignore proxy environment and reject redirects: synthetic audio stays local.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("LOCAL_STT_REDIRECT_REJECTED")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=60) as response:
        payload = json.loads(response.read(1_000_000))
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        raise TypeError("INVALID_LOCAL_STT_RESPONSE")
    return {
        "status": "transcribed",
        "text": payload["text"],
        "language": "de",
        "engine": "resident local Parakeet TDT 0.6b v3 q8_0 CPU",
        "endpoint": "127.0.0.1:8040",
        "humanVerified": False,
    }


def build_audit(root: Path, run_stt: bool) -> dict:
    review = root / "review"
    cache_path = review / "audit.json"
    cached = (
        json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_path.exists()
        else {}
    )
    previous = {
        row["signal"]["sha256"]: row["stt"]
        for row in cached.get("samples", [])
        if row.get("stt", {}).get("status") == "transcribed"
    }
    sources = {
        engine: json.loads((root / engine / "results.json").read_text(encoding="utf-8"))
        for engine in ENGINES
    }
    texts = sources["chatterbox"]["metadata"]["texts"]
    if set(texts) != set(CASES) or sources["moss"]["metadata"]["texts"] != texts:
        raise ValueError("EXPECTED_TEXTS_DIFFER_BETWEEN_ENGINES")
    rows = []
    for engine, source in sources.items():
        seen = set()
        for row in source["runs"]:
            case, iteration = row["case"], row["iteration"]
            if (
                case not in CASES
                or type(iteration) is not int
                or iteration not in range(4)
                or (case, iteration) in seen
            ):
                raise ValueError("INVALID_OR_DUPLICATE_RUN")
            seen.add((case, iteration))
            expected_name = f"{case}-{iteration}.wav"
            if row["wav"] != expected_name:
                raise ValueError("UNEXPECTED_WAV_PATH")
            path = root / engine / expected_name
            signal = inspect_wav(path, row["sha256"])
            if abs(signal["audioSeconds"] - row["audioSeconds"]) > 1e-6:
                raise ValueError("RECORDED_DURATION_MISMATCH")
            stt = previous.get(signal["sha256"], {"status": "not_requested"})
            if run_stt and stt.get("status") != "transcribed":
                try:
                    stt = transcribe(path)
                except (OSError, TypeError, ValueError) as error:
                    stt = {"status": "failed", "code": type(error).__name__}
            rows.append(
                {
                    "id": f"{engine}-{case}-{iteration}",
                    "engine": engine,
                    "case": case,
                    "iteration": iteration,
                    "expectedText": texts[case],
                    "inputSha256": hashlib.sha256(texts[case].encode()).hexdigest(),
                    "sourceWav": f"{engine}/{expected_name}",
                    "run": row,
                    "seed": 82000 + iteration if engine == "moss" else None,
                    "signal": signal,
                    "stt": stt,
                }
            )
            review.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({"samples": rows}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(
                json.dumps({"id": rows[-1]["id"], "stt": stt.get("status")}), flush=True
            )
        if len(seen) != 12:
            raise ValueError("EXACTLY_TWELVE_RUNS_PER_ENGINE_REQUIRED")
    replay = review / "moss-input-preparation.json"
    return {
        "selectionRule": "First warm run (iteration 1) for both engines in every case, never chosen by quality or speed. All 24 original runs retained.",
        "blindOrder": {
            case: dict(zip(("A", "B"), engines)) for case, engines in ORDER.items()
        },
        "blindingLimit": "Identities hidden by presentation only; source/manifest reveals mapping. Native player duration is visible.",
        "configuration": CONFIG,
        "configurationProvenance": "a842b9e benchmark runner and preserved report; no new synthesis",
        "referenceSha256": REFERENCE_SHA,
        "mossTextPreparationReplay": json.loads(replay.read_text(encoding="utf-8"))
        if replay.is_file()
        else None,
        "benchmarkMetadata": {
            engine: source["metadata"] for engine, source in sources.items()
        },
        "samples": rows,
    }


def render(root: Path, audit: dict, language: str) -> Path:
    locales = json.loads(
        Path(__file__)
        .with_name("tts-listening-locales.json")
        .read_text(encoding="utf-8")
    )
    labels = locales["en"] | locales[language]
    esc = html.escape

    def t(key):
        return esc(labels[key])

    review = root / "review"
    (review / "audio").mkdir(exist_ok=True)
    samples = {row["id"]: row for row in audit["samples"]}
    body = [f"<h1>{t('title')}</h1><p>{t('intro')}</p><p>{t('rule')}</p>"]
    for case in CASES:
        body.append(
            f'<section><h2>{t(case)}</h2><p class="expected">{esc(samples[f"chatterbox-{case}-1"]["expectedText"])}</p><div class="pair">'
        )
        for variant, engine in zip(("A", "B"), ORDER[case]):
            row = samples[f"{engine}-{case}-1"]
            name = f"{case}-{variant}.wav"
            shutil.copyfile(root / row["sourceWav"], review / "audio" / name)
            body.append(
                f'<article><h3>{variant}</h3><audio controls preload="metadata" src="audio/{name}"></audio>'
            )
            for criterion in ("complete", "clear", "natural", "voice"):
                body.append(
                    f'<label>{t(criterion)} <select id="{case}-{variant}-{criterion}"><option value="">{t("unrated")}</option>'
                    + "".join(f"<option>{i}</option>" for i in range(1, 6))
                    + "</select></label>"
                )
            body.append("</article>")
        body.append(
            f'</div><label>{t("choice")} <select id="{case}-choice">'
            + "".join(
                f'<option value="{key}">{t(key)}</option>'
                for key in ("unrated", "A", "B", "both", "neither")
            )
            + f'</select></label><label>{t("notes")}<textarea id="{case}-notes" rows="3"></textarea></label></section>'
        )
    body.append(
        f'<p>{t("scale")}</p><button id="export">{t("export")}</button><p>{t("local")}</p><details><summary>{t("reveal")}</summary><p>{t("sttNote")}</p>'
    )
    for case in CASES:
        body.append(f"<h2>{t(case)}</h2><ul>")
        for variant, engine in zip(("A", "B"), ORDER[case]):
            row = samples[f"{engine}-{case}-1"]
            body.append(
                f"<li>{variant}: {esc(CONFIG[engine]['engine'])}; {t('synthesis')}: {row['run']['totalSeconds']:.3f}s; {t('duration')}: {row['signal']['audioSeconds']:.2f}s</li>"
            )
        body.append("</ul>")
    body.append(f'<p><a href="audit.json">{t("manifest")}</a></p><h2>{t("extra")}</h2>')
    for row in audit["samples"]:
        name = row["id"] + ".wav"
        shutil.copyfile(root / row["sourceWav"], review / "audio" / name)
        transcript = row["stt"].get("text", row["stt"]["status"])
        body.append(
            f'<details><summary>{esc(row["id"])} — {row["signal"]["audioSeconds"]:.2f}s</summary><audio controls preload="none" src="audio/{name}"></audio><p>{t("stt")}: {esc(transcript)}</p><p>SHA256: <code>{row["signal"]["sha256"]}</code></p></details>'
        )
    body.append("</details>")
    page = f'''<!doctype html><html lang="{language}"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; media-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>{t("title")}</title><style>body{{font:17px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#18252d;background:#fafaf8}}section{{border-top:1px solid #aab;padding:1rem 0}}.pair{{display:flex;gap:2rem;flex-wrap:wrap}}article{{flex:1;min-width:280px}}label{{display:block;margin:.7rem 0}}audio,textarea{{width:100%}}.expected{{white-space:pre-line;background:#eef2ed;padding:1rem}}select,button,textarea{{font:inherit}}summary{{cursor:pointer;padding:.6rem 0}}code{{overflow-wrap:anywhere}}</style><main>{"".join(body)}</main><script src="review.js"></script></html>'''
    (review / "index.html").write_text(page, encoding="utf-8")
    shutil.copyfile(
        Path(__file__).with_name("tts-listening-review.js"), review / "review.js"
    )
    (review / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return review / "index.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(".run/dev-recovery/tts-isolated")
    )
    parser.add_argument(
        "--transcribe",
        action="store_true",
        help="Sequential local STT on existing synthetic audio only; cache by WAV SHA256",
    )
    parser.add_argument("--language", choices=("de", "en"), default="de")
    args = parser.parse_args()
    print(render(args.root, build_audit(args.root, args.transcribe), args.language))
