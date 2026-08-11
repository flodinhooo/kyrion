"""Generate the twelve review-only Fixed Velora candidates with stock XTTS v2."""

from __future__ import annotations

import hashlib
import json
import platform
import random
import time
import wave
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from TTS.api import TTS


REFERENCE = Path(
    "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"
)
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
OUTPUT_ROOT = Path(
    "/mnt/e/Kyrion/Data/voice-training/fixed-responses/velora"
)
MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"
SAMPLE_RATE = 24_000

ASSETS = (
    ("de", "session.greeting", "neutral-01", "Hallo."),
    ("de", "session.greeting", "warm-01", "Hallo, schön dich zu hören."),
    ("en", "session.greeting", "neutral-01", "Hello."),
    ("en", "session.greeting", "warm-01", "Hello, good to hear you."),
    ("de", "session.farewell", "neutral-01", "Bis später."),
    ("de", "session.farewell", "warm-01", "Mach's gut."),
    ("en", "session.farewell", "neutral-01", "Talk to you later."),
    ("en", "session.farewell", "warm-01", "Take care."),
    ("de", "dialogue.acknowledged", "neutral-01", "Okay."),
    ("de", "dialogue.acknowledged", "neutral-02", "Alles klar."),
    ("en", "dialogue.acknowledged", "neutral-01", "Okay."),
    ("en", "dialogue.acknowledged", "neutral-02", "Got it."),
)


def main() -> None:
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora reference checksum mismatch")

    load_started = time.perf_counter()
    runtime = TTS(MODEL_ID).to("cuda")
    load_seconds = time.perf_counter() - load_started
    results: list[dict[str, object]] = []

    for index, (locale, response_key, variant_id, text) in enumerate(ASSETS, start=1):
        seed = 84_000 + index
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        target = OUTPUT_ROOT / locale / response_key / f"{variant_id}.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        samples = np.asarray(
            runtime.tts(
                text=text,
                speaker_wav=str(REFERENCE),
                language=locale,
                split_sentences=False,
            ),
            dtype=np.float32,
        ).reshape(-1)
        synthesis_seconds = time.perf_counter() - started
        sf.write(target, samples, SAMPLE_RATE, subtype="PCM_16")
        with wave.open(str(target), "rb") as wav_file:
            metadata = {
                "sampleRateHz": wav_file.getframerate(),
                "channels": wav_file.getnchannels(),
                "sampleWidthBytes": wav_file.getsampwidth(),
                "frames": wav_file.getnframes(),
                "durationSeconds": wav_file.getnframes() / wav_file.getframerate(),
            }
        if metadata["sampleRateHz"] != SAMPLE_RATE or metadata["channels"] != 1 or metadata["sampleWidthBytes"] != 2:
            raise RuntimeError(f"Unexpected WAV format: {target}")
        results.append(
            {
                "order": index,
                "locale": locale,
                "responseKey": response_key,
                "variantId": variant_id,
                "text": text,
                "seed": seed,
                "path": str(target),
                "classification": "pending_manual_review",
                "synthesisSeconds": synthesis_seconds,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                **metadata,
            }
        )
        print(f"[{index:02d}/12] {target}", flush=True)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "generation-results.json").write_text(
        json.dumps(
            {
                "status": "pending_manual_review",
                "registered": False,
                "productionAssets": False,
                "engine": "XTTS v2 stock TTS API",
                "model": MODEL_ID,
                "reference": str(REFERENCE),
                "referenceSha256": REFERENCE_SHA256,
                "modelLoadSeconds": load_seconds,
                "runtime": {"python": platform.python_version(), "torch": torch.__version__},
                "assets": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
