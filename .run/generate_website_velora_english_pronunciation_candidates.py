"""Generate English Velora pronunciation candidates with the canonical voice."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


REFERENCE = "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"
MODEL = "/training/models/qwen3-tts/voice-clone-base"
OUTPUT = Path("/mnt/e/Kyrion/Data/voice-training/website-velora-english-candidates")
REFERENCE_TEXT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner "
    "Liste. Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
INSTRUCTION = (
    "Speak neutral international English with a warm, calm, confident adult female voice. "
    "Use natural English rhythm, connected phrasing, relaxed English vowels and English intonation. "
    "Do not sound like a German speaker reading English. Keep the exact cloned Velora speaker identity. "
    "Pronounce Kyrion as three smooth syllables, KÜ-ri-on, with no pause between syllables."
)
CANDIDATES = {
    "en-06-velaura": "Hi, I’m Velaura — the voice of Kü-ri-on. It’s nice to meet you.",
    "en-07-vay-laura": "Hi, I’m Vay-laura — the voice of Kü-ri-on. It’s nice to meet you.",
    "en-08-veh-law-ra": "Hi, I’m Veh-law-ra — the voice of Kü-ri-on. It’s nice to meet you.",
    "en-09-vuh-lor-uh": "Hi, I’m Vuh-LOR-uh — the voice of Kü-ri-on. It’s nice to meet you.",
}


def trim_and_normalize(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    active = np.flatnonzero(np.abs(samples) >= 10 ** (-48 / 20))
    if active.size:
        padding = int(sample_rate * 0.12)
        samples = samples[max(0, int(active[0]) - padding) : min(sample_rate * 20, int(active[-1]) + padding + 1)]
    peak = float(np.max(np.abs(samples), initial=0.0))
    if peak > 0:
        samples = samples * (10 ** (-1 / 20)) / peak
    return samples


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    prompt = model.create_voice_clone_prompt(ref_audio=REFERENCE, ref_text=REFERENCE_TEXT)
    results = []
    for index, (candidate_id, text) in enumerate(CANDIDATES.items(), start=6):
        torch.manual_seed(42042 + index)
        started = time.perf_counter()
        print(f"Generating {candidate_id}", flush=True)
        wavs, sample_rate = model.generate_voice_clone(
            text=text,
            language="English",
            voice_clone_prompt=prompt,
            max_new_tokens=1024,
        )
        audio = trim_and_normalize(wavs[0], sample_rate)
        target = OUTPUT / f"{candidate_id}.wav"
        sf.write(target, audio, sample_rate, subtype="PCM_16")
        results.append(
            {
                "id": candidate_id,
                "language": "English",
                "text": text,
                "instruction": INSTRUCTION,
                "path": str(target),
                "sampleRateHz": sample_rate,
                "durationSeconds": len(audio) / sample_rate,
                "generationSeconds": time.perf_counter() - started,
                "seed": 42042 + index,
            }
        )
    (OUTPUT / "candidates.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
