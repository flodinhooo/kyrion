from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


MODEL = "/training/models/qwen3-tts/voice-clone-base"
SOURCE = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-voice-finalists")
OUTPUT = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-voice-clone-finalists")
REFERENCE_TEXT = (
    "Hallo, ich bin Velora. Schön, dass du da bist. "
    "Womit möchtest du heute anfangen?"
)
VOICES = {
    "04b": SOURCE / "04b_tief_sanft.wav",
    "05a": SOURCE / "05a_modern_klar.wav",
    "06b": SOURCE / "06b_reif_elegant.wav",
}
TESTS = {
    "dialog": (
        "Natürlich. Ich habe das Licht im Wohnzimmer noch nicht verändert. "
        "Soll ich es auf dreißig Prozent dimmen und anschließend die Musik leiser stellen?"
    ),
    "aussprache": (
        "Um fünfzehn Uhr dreißig werden draußen zwölf Grad erwartet. "
        "Überprüfe bitte Küche, Schlafzimmer und Gästezimmer, bevor du die Tür abschließt."
    ),
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    for voice, reference in VOICES.items():
        prompt = model.create_voice_clone_prompt(
            ref_audio=str(reference),
            ref_text=REFERENCE_TEXT,
        )
        for test_name, text in TESTS.items():
            print(f"Generating {voice}_{test_name}", flush=True)
            wavs, sample_rate = model.generate_voice_clone(
                text=text,
                language="German",
                voice_clone_prompt=prompt,
                max_new_tokens=1024,
            )
            sf.write(OUTPUT / f"{voice}_{test_name}.wav", wavs[0], sample_rate)


if __name__ == "__main__":
    main()
