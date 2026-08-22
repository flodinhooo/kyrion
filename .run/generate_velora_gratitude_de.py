"""Generate review-only German Velora gratitude-response candidates."""

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
OUTPUT = Path("/mnt/e/Kyrion/Data/voice-production/velora-gratitude-de-v1/review-candidates")
LINES = [
    ("session.gratitude_neutral-01", "Kein Problem!"),
    ("session.gratitude_neutral-02", "Gern geschehen."),
    ("session.gratitude_warm-01", "Sehr gerne."),
    ("session.gratitude_helpful-01", "Gib Bescheid, wenn ich noch etwas für dich tun kann."),
    ("session.gratitude_warm-02", "Immer gerne."),
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
    (OUTPUT / "catalog.json").write_text(json.dumps({
        "schemaVersion": 1,
        "status": "review_only",
        "model": MODEL,
        "referenceSha256": REFERENCE_SHA256,
        "candidatesPerLine": 2,
        "lines": [{"id": key, "text": text} for key, text in LINES],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    model = Qwen3TTSModel.from_pretrained(
        MODEL, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa"
    )
    prompt = model.create_voice_clone_prompt(ref_audio=str(REFERENCE), ref_text=REFERENCE_TEXT)
    for line_index, (key, spoken_text) in enumerate(LINES, start=1):
        for candidate in range(1, 3):
            target = OUTPUT / f"{key}__candidate-{candidate:02d}.wav"
            if target.exists():
                continue
            torch.manual_seed(2026082200 + line_index * 10 + candidate)
            started = time.perf_counter()
            wavs, sample_rate = model.generate_voice_clone(
                text=spoken_text, language="German", voice_clone_prompt=prompt,
                max_new_tokens=1024,
            )
            sf.write(target, wavs[0], sample_rate, subtype="PCM_16")
            print(json.dumps({
                "file": target.name,
                "seconds": round(time.perf_counter() - started, 3),
                "sha256": sha256(target),
            }), flush=True)


if __name__ == "__main__":
    main()
