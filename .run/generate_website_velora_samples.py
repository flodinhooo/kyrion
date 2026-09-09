"""Generate review-only website samples with the canonical Velora voice."""

from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


REFERENCE = "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"
MODEL = "/training/models/qwen3-tts/voice-clone-base"
OUTPUT = Path("/mnt/e/Kyrion/Data/voice-training/website-velora-intro")
REFERENCE_TEXT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner "
    "Liste. Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
SAMPLES = {
    "velora-intro-de": (
        "Hallo, ich bin Velora – die Stimme von Kyrion. Schön, dich kennenzulernen.",
        "German",
    ),
    "velora-intro-en": (
        "Hi, I'm Velora — the voice of Kyrion. It's nice to meet you.",
        "English",
    ),
}


def trim_and_normalize(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    threshold = 10 ** (-48 / 20)
    active = np.flatnonzero(np.abs(samples) >= threshold)
    if active.size:
        padding = int(sample_rate * 0.12)
        start = max(0, int(active[0]) - padding)
        end = min(samples.size, int(active[-1]) + padding + 1)
        samples = samples[start:end]
    peak = float(np.max(np.abs(samples), initial=0.0))
    if peak > 0:
        samples = samples * (10 ** (-1 / 20)) / peak
    return samples


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(42042)
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    prompt = model.create_voice_clone_prompt(
        ref_audio=REFERENCE,
        ref_text=REFERENCE_TEXT,
    )
    for name, (text, language) in SAMPLES.items():
        print(f"Generating {name}", flush=True)
        wavs, sample_rate = model.generate_voice_clone(
            text=text,
            language=language,
            voice_clone_prompt=prompt,
            max_new_tokens=1024,
        )
        audio = trim_and_normalize(wavs[0], sample_rate)
        sf.write(OUTPUT / f"{name}.wav", audio, sample_rate, subtype="PCM_16")
        print(f"Wrote {OUTPUT / f'{name}.wav'} at {sample_rate} Hz", flush=True)


if __name__ == "__main__":
    main()
