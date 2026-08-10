"""Live XTTS inference_stream guard spike; isolated from Kyrion services."""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import threading
import time
import wave
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np
import torch
from faster_whisper import WhisperModel
from TTS.api import TTS

ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
RATE = 24_000
PREBUFFER = 0.320
CHUNK_TOKENS = 20
PARAMETERS = {
    "temperature": 0.75,
    "length_penalty": 1.0,
    "repetition_penalty": 10.0,
    "top_k": 50,
    "top_p": 0.85,
}
TEXTS = {
    "short-de": ("de", "Ich bin Velora."),
    "medium-de": ("de", "Ich bin Velora und begleite dich durch deinen Alltag."),
    "long-de": (
        "de",
        "Natürlich, Flo. Ich helfe dir dabei, den Überblick zu behalten und die nächsten Schritte in Ruhe zu planen. Sag mir einfach, womit wir beginnen sollen.",
    ),
    "dialogue-de": (
        "de",
        "Ja, Madrid ist die Hauptstadt Spaniens. Barcelona ist ebenfalls sehr bedeutend, aber Madrid wurde zum politischen und administrativen Zentrum des Landes.",
    ),
    "numbers-de": ("de", "Heute sind es 21,5 Grad. Der Termin beginnt um 14:35 Uhr."),
    "numbers-en": ("en", "It is 21.5 degrees. Your appointment starts at 2:35 p.m."),
    "domain-de": ("de", "Velora, schalte bitte die desk lamp im Gamingraum ein."),
    "domain-en": ("en", "Velora, turn on the desk lamp in the gaming room, please."),
    "pause-de": (
        "de",
        "Velora, warte kurz. Die desk lamp im Gamingraum bleibt an, und danach planen wir in Ruhe weiter.",
    ),
    "pause-en": (
        "en",
        "Velora, wait a moment. Keep the desk lamp in the gaming room on, and then continue calmly.",
    ),
}


def norm(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def resample_16k(audio: np.ndarray) -> np.ndarray:
    return np.interp(
        np.linspace(0, len(audio) - 1, round(len(audio) * 2 / 3)),
        np.arange(len(audio)),
        audio,
    ).astype(np.float32)


def silence_cutoff(audio: np.ndarray, after: float) -> float | None:
    frame = round(0.02 * RATE)
    rms = np.array(
        [
            np.sqrt(np.mean(audio[i : i + frame] ** 2))
            for i in range(0, len(audio), frame)
            if len(audio[i : i + frame])
        ]
    )
    quiet = rms < 10 ** (-40 / 20)
    for index in range(max(0, round(after / 0.02)), len(quiet) - 14):
        if quiet[index : index + 15].all():
            return index * 0.02 + 0.20
    return None


def write_wav(path: Path, audio: np.ndarray) -> None:
    pcm = np.clip(audio * 32767, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as target:
        target.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        target.writeframes(pcm.tobytes())


def playback(releases: list[dict[str, Any]]) -> dict[str, Any]:
    if not releases:
        return {"ttfaSeconds": None, "underruns": 1, "minimumBufferSeconds": 0.0}
    total = 0.0
    start = None
    for index, item in enumerate(releases):
        total += item["samples"] / RATE
        if total >= PREBUFFER:
            start = index
            break
    if start is None:
        return {"ttfaSeconds": None, "underruns": 1, "minimumBufferSeconds": 0.0}
    buffer = sum(item["samples"] for item in releases[: start + 1]) / RATE
    minimum = buffer
    previous = releases[start]["atSeconds"]
    underruns = 0
    for item in releases[start + 1 :]:
        buffer -= item["atSeconds"] - previous
        minimum = min(minimum, buffer)
        if buffer < 0:
            underruns += 1
            buffer = 0.0
        buffer += item["samples"] / RATE
        previous = item["atSeconds"]
    return {
        "ttfaSeconds": round(releases[start]["atSeconds"], 6),
        "underruns": underruns,
        "minimumBufferSeconds": round(max(0, minimum), 6),
    }


def run(
    model: Any,
    guard_asr: WhisperModel,
    conditioning: tuple[Any, Any],
    text_id: str,
    run_index: int,
    output: Path,
) -> dict[str, Any]:
    language, text = TEXTS[text_id]
    seed = 30_000 + run_index
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    started = time.perf_counter()
    cancel = threading.Event()
    stream_queue: queue.Queue[Any] = queue.Queue(maxsize=1)
    producer_events: list[dict[str, Any]] = []
    producer_done = threading.Event()

    def produce() -> None:
        generator = model.inference_stream(
            text,
            language,
            *conditioning,
            stream_chunk_size=CHUNK_TOKENS,
            overlap_wav_len=1024,
            do_sample=True,
            **PARAMETERS,
        )
        try:
            for index, tensor in enumerate(generator):
                torch.cuda.synchronize()
                at = time.perf_counter() - started
                audio = tensor.detach().float().cpu().numpy()
                event = {
                    "index": index,
                    "atSeconds": at,
                    "samples": len(audio),
                    "afterDecision": cancel.is_set(),
                }
                producer_events.append(event)
                if cancel.is_set():
                    break
                stream_queue.put((index, at, audio))
        finally:
            generator.close()
            stream_queue.put(None)
            producer_done.set()

    thread = threading.Thread(target=produce, daemon=True)
    thread.start()
    cumulative = np.zeros(0, np.float32)
    released = 0
    releases: list[dict[str, Any]] = []
    checks = []
    content_match = None
    decision = None
    cutoff_samples = None
    pending_end = 0
    expected = norm(text)
    expected_words = len(expected.split())
    while True:
        item = stream_queue.get()
        if item is None:
            break
        index, _arrived, audio = item
        cumulative = np.concatenate((cumulative, audio))
        pending_end = len(cumulative)
        check_started = time.perf_counter()
        segments, _ = guard_asr.transcribe(
            resample_16k(cumulative),
            language=language,
            beam_size=1,
            temperature=0.0,
            condition_on_previous_text=False,
            word_timestamps=True,
            vad_filter=False,
        )
        words = [word for segment in segments for word in segment.words]
        transcript = " ".join(word.word.strip() for word in words)
        observed = norm(transcript)
        prefix = " ".join(observed.split()[:expected_words])
        score = SequenceMatcher(None, expected, prefix).ratio()
        latency = time.perf_counter() - check_started
        checked_at = time.perf_counter() - started
        matched = len(prefix.split()) >= expected_words and score >= 0.78
        if matched and content_match is None:
            content_match = checked_at
        cutoff = (
            silence_cutoff(cumulative, words[expected_words - 1].end)
            if matched and len(words) >= expected_words
            else None
        )
        checks.append(
            {
                "chunk": index,
                "audioAvailableSeconds": round(len(cumulative) / RATE, 6),
                "startedSeconds": round(check_started - started, 6),
                "latencySeconds": round(latency, 6),
                "completedSeconds": round(checked_at, 6),
                "transcript": transcript,
                "alignmentScore": round(score, 4),
                "contentMatched": matched,
                "silenceCutoffSeconds": cutoff,
            }
        )
        if cutoff is not None:
            cutoff_samples = min(round(cutoff * RATE), len(cumulative))
            decision = time.perf_counter() - started
            cancel.set()
            if cutoff_samples > released:
                releases.append(
                    {"atSeconds": decision, "samples": cutoff_samples - released}
                )
                released = cutoff_samples
            break
        # One real XTTS chunk remains withheld as safety lookahead.
        safe_end = len(cumulative) - len(audio)
        if safe_end > released:
            releases.append({"atSeconds": checked_at, "samples": safe_end - released})
            released = safe_end
    if decision is None and pending_end > released:
        now = time.perf_counter() - started
        releases.append({"atSeconds": now, "samples": pending_end - released})
        released = pending_end
    if decision is not None:
        # Unblock a producer that completed a lookahead chunk while ASR was
        # deciding. These items are deliberately discarded, never released.
        while not producer_done.is_set():
            try:
                stream_queue.get(timeout=0.1)
            except queue.Empty:
                pass
    thread.join()
    cancellation = time.perf_counter() - started if cancel.is_set() else None
    playable = cumulative[:released]
    total = time.perf_counter() - started
    duration = len(playable) / RATE
    target = output / f"{text_id}--run-{run_index}.wav"
    write_wav(target, playable)
    post_decision_generated = sum(
        event["samples"] for event in producer_events if event["afterDecision"]
    )
    result = {
        "textId": text_id,
        "language": language,
        "text": text,
        "run": run_index,
        "seed": seed,
        "wav": str(target),
        "generatedPcmSeconds": round(
            sum(e["samples"] for e in producer_events) / RATE, 6
        ),
        "consumerBufferedPcmAtDecisionSeconds": round((pending_end - released) / RATE, 6)
        if decision
        else 0.0,
        "playableReleasedSeconds": round(duration, 6),
        "contentMatchSeconds": round(content_match, 6) if content_match else None,
        "guardDecisionSeconds": round(decision, 6) if decision else None,
        "generatorCancellationSeconds": round(cancellation, 6)
        if cancellation
        else None,
        "postDecisionGeneratedSeconds": round(post_decision_generated / RATE, 6),
        "postDecisionReleasedSeconds": 0.0,
        "checks": checks,
        "asrLatencyMedianSeconds": round(
            float(np.median([c["latencySeconds"] for c in checks])), 6
        ),
        "asrLatencyP95Seconds": round(
            float(np.percentile([c["latencySeconds"] for c in checks], 95)), 6
        ),
        "totalSeconds": round(total, 6),
        "rtf": round(total / duration, 6),
        **playback(releases),
    }
    print(
        f"{text_id} run={run_index} decision={result['guardDecisionSeconds']} playable={duration:.3f}s ttfa={result['ttfaSeconds']} rtf={result['rtf']:.3f} underruns={result['underruns']}",
        flush=True,
    )
    return result


def save_results(output: Path, runs: list[dict[str, Any]]) -> None:
    (output / "results.json").write_text(
        json.dumps(
            {
                "referenceSha256": REFERENCE_SHA256,
                "parameters": PARAMETERS,
                "runs": runs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/training/xtts-v2-live-guard-spike")
    )
    args = parser.parse_args()
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(REFERENCE)])
    guard_asr = WhisperModel("small", device="cpu", compute_type="int8")
    list(
        model.inference_stream(
            "Systemstart.",
            "de",
            *conditioning,
            stream_chunk_size=CHUNK_TOKENS,
            **PARAMETERS,
        )
    )
    list(guard_asr.transcribe(np.zeros(16000, np.float32), language="de"))[0:0]
    runs = []
    for index in range(1, 11):
        runs.append(run(model, guard_asr, conditioning, "short-de", index, args.output))
        save_results(args.output, runs)
    for text_id in TEXTS:
        if text_id != "short-de":
            runs.append(run(model, guard_asr, conditioning, text_id, 1, args.output))
            save_results(args.output, runs)


if __name__ == "__main__":
    main()
