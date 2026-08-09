from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


OUTPUT = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-voice-samples")
MODEL = Path(
    "/training/models/qwen3-tts/voice-design-complete"
)
TEXT = (
    "Hallo, ich bin Velora. Wie kann ich dir helfen? "
    "Wenn du möchtest, können wir direkt gemeinsam loslegen."
)
VOICES = {
    "01_warm_natural": "A warm, natural adult German female voice, calm, trustworthy and conversational, with clear articulation and no exaggerated emotion.",
    "02_soft_elegant": "An elegant adult German female voice, soft and smooth, with a refined timbre and relaxed pacing.",
    "03_bright_friendly": "A bright, friendly young adult German female voice, approachable and lively, but not childish.",
    "04_deep_calm": "A lower-pitched adult German female voice, calm, grounded and confident, with gentle warmth.",
    "05_modern_assistant": "A modern German female assistant voice, natural and intelligent, concise, clear and subtly warm.",
    "06_mature_warm": "A mature German female voice with a rich warm timbre, reassuring, patient and natural.",
    "07_clear_neutral": "A neutral adult German female voice with excellent clarity, balanced pitch and natural conversational rhythm.",
    "08_gentle_intimate": "A gentle German female voice, close and personable, softly spoken but fully clear, with natural emotion.",
    "09_confident_dynamic": "A confident adult German female voice with energetic but controlled delivery and a crisp modern timbre.",
    "10_velora_candidate": "A distinctive premium German female voice for an intelligent home companion: warm, composed, natural, subtly futuristic, never robotic or theatrical.",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = Qwen3TTSModel.from_pretrained(
        str(MODEL),
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
        cache_dir="/training/models/qwen3-tts",
    )
    for name, description in VOICES.items():
        print(f"Generating {name}", flush=True)
        wavs, sample_rate = model.generate_voice_design(
            text=TEXT,
            language="German",
            instruct=description,
            max_new_tokens=768,
        )
        sf.write(OUTPUT / f"{name}.wav", wavs[0], sample_rate)


if __name__ == "__main__":
    main()
