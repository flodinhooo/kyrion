"""Generate pronunciation candidates without touching the website production assets."""

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
OUTPUT = Path("/mnt/e/Kyrion/Data/voice-training/website-velora-pronunciation-candidates")
REFERENCE_TEXT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner "
    "Liste. Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
DE_INSTRUCTION = (
    "Sprich natürliches, akzentfreies Standarddeutsch mit warmer, ruhiger und sicherer "
    "weiblicher Stimme. Keine Werbestimme, keine übertriebene Emotion. Das Kunstwort "
    "Kyrion wird in drei flüssigen Silben als KÜ-ri-on gesprochen, mit natürlicher "
    "Betonung auf KÜ und ohne hörbare Trennpausen."
)
EN_INSTRUCTION = (
    "Speak neutral international English with a warm, calm, confident adult female voice. "
    "Use natural English rhythm, connected phrasing, English intonation and relaxed vowels; "
    "do not sound like a German speaker reading English. Keep the cloned Velora speaker identity. "
    "The brand name Kyrion must remain three smooth syllables, KÜ-ri-on, with the same pronunciation "
    "as in German and no pause between syllables."
)

CANDIDATES = [
    {
        "id": "de-01-display",
        "language": "German",
        "instruction": DE_INSTRUCTION,
        "text": "Hallo, ich bin Velora – die Stimme von Kyrion. Schön, dich kennenzulernen.",
    },
    {
        "id": "de-02-kurion",
        "language": "German",
        "instruction": DE_INSTRUCTION,
        "text": "Hallo, ich bin Velora – die Stimme von Kürion. Schön, dich kennenzulernen.",
    },
    {
        "id": "de-03-kueri-on",
        "language": "German",
        "instruction": DE_INSTRUCTION,
        "text": "Hallo, ich bin Velora – die Stimme von Kü-ri-on. Schön, dich kennenzulernen.",
    },
    {
        "id": "en-01-display",
        "language": "English",
        "instruction": EN_INSTRUCTION,
        "text": "Hi, I’m Velora — the voice of Kyrion. It’s nice to meet you.",
    },
    {
        "id": "en-02-kueri-on",
        "language": "English",
        "instruction": EN_INSTRUCTION,
        "text": "Hi, I’m Velora — the voice of Kü-ri-on. It’s nice to meet you.",
    },
    {
        "id": "en-03-kuerion",
        "language": "English",
        "instruction": EN_INSTRUCTION,
        "text": "Hi, I’m Velora — the voice of Kürion. It’s nice to meet you.",
    },
    {
        "id": "en-04-kyrion",
        "language": "English",
        "instruction": EN_INSTRUCTION,
        "text": "Hi, I’m Velora — the voice of Kyu-ri-on. It’s nice to meet you.",
    },
    {
        "id": "en-05-velora-guided",
        "language": "English",
        "instruction": EN_INSTRUCTION
        + " Pronounce Velora naturally in English as Veh-LOH-rah, without a German vowel pattern.",
        "text": "Hi, I’m Veh-LOH-rah — the voice of Kü-ri-on. It’s nice to meet you.",
    },
]


def trim_and_normalize(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    active = np.flatnonzero(np.abs(samples) >= 10 ** (-48 / 20))
    if active.size:
        padding = int(sample_rate * 0.12)
        samples = samples[max(0, int(active[0]) - padding) : min(samples.size, int(active[-1]) + padding + 1)]
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
    results: list[dict[str, object]] = []
    for index, candidate in enumerate(CANDIDATES, start=1):
        torch.manual_seed(42042 + index)
        started = time.perf_counter()
        print(f"[{index}/{len(CANDIDATES)}] Generating {candidate['id']}", flush=True)
        wavs, sample_rate = model.generate_voice_clone(
            text=candidate["text"],
            language=candidate["language"],
            voice_clone_prompt=prompt,
            max_new_tokens=1024,
        )
        audio = trim_and_normalize(wavs[0], sample_rate)
        target = OUTPUT / f"{candidate['id']}.wav"
        sf.write(target, audio, sample_rate, subtype="PCM_16")
        results.append(
            {
                **candidate,
                "path": str(target),
                "sampleRateHz": sample_rate,
                "durationSeconds": len(audio) / sample_rate,
                "generationSeconds": time.perf_counter() - started,
                "seed": 42042 + index,
            }
        )
    (OUTPUT / "candidates.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote metadata to {OUTPUT / 'candidates.json'}", flush=True)


if __name__ == "__main__":
    main()
