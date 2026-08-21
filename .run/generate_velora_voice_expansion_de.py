"""Generate review-only German Velora greeting and action-processing candidates."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

MODEL = "/training/models/qwen3-tts/voice-clone-base"
REFERENCE = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav")
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
REFERENCE_TEXT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
OUTPUT = Path("/mnt/e/Kyrion/Data/voice-production/velora-expansion-de-v1/review-candidates")
CANDIDATES_PER_LINE = 2
LINES = [
    ("session.greeting_friendly-01", "Hey, schön, dass du da bist."),
    ("session.greeting_ready-01", "Hallo, ich bin bereit."),
    ("session.greeting_warm-02", "Schön, von dir zu hören."),
    ("session.greeting_helpful-01", "Hey, was kann ich für dich tun?"),
    ("action.processing_neutral-01", "Klar, gib mir einen Augenblick."),
    ("action.processing_neutral-02", "Alles klar, ich kümmere mich darum."),
    ("action.processing_neutral-03", "Verstanden, einen Moment bitte."),
    ("action.processing_warm-01", "Gerne, ich kümmere mich darum."),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if sha256(REFERENCE) != REFERENCE_SHA256:
        raise RuntimeError("Canonical velora-f reference checksum mismatch")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schemaVersion": 1,
        "status": "review_only",
        "model": MODEL,
        "reference": str(REFERENCE),
        "referenceSha256": REFERENCE_SHA256,
        "referenceText": REFERENCE_TEXT,
        "candidatesPerLine": CANDIDATES_PER_LINE,
        "lines": [{"id": key, "text": text} for key, text in LINES],
    }
    (OUTPUT / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    model = Qwen3TTSModel.from_pretrained(
        MODEL, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa"
    )
    prompt = model.create_voice_clone_prompt(ref_audio=str(REFERENCE), ref_text=REFERENCE_TEXT)
    for line_index, (key, spoken_text) in enumerate(LINES, start=1):
        for candidate in range(1, CANDIDATES_PER_LINE + 1):
            target = OUTPUT / f"{key}__candidate-{candidate:02d}.wav"
            if target.exists():
                print(f"SKIP {target.name}", flush=True)
                continue
            seed = 2026082100 + line_index * 10 + candidate
            torch.manual_seed(seed)
            started = time.perf_counter()
            wavs, sample_rate = model.generate_voice_clone(
                text=spoken_text,
                language="German",
                voice_clone_prompt=prompt,
                max_new_tokens=1024,
            )
            sf.write(target, wavs[0], sample_rate, subtype="PCM_16")
            result = {
                "id": key,
                "text": spoken_text,
                "candidate": candidate,
                "seed": seed,
                "path": str(target),
                "sampleRateHz": sample_rate,
                "durationSeconds": len(wavs[0]) / sample_rate,
                "generationSeconds": time.perf_counter() - started,
                "sha256": sha256(target),
            }
            with (OUTPUT / "generation-results.ndjson").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"DONE {target.name}", flush=True)


if __name__ == "__main__":
    main()
