from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


MODEL = "/training/models/qwen3-tts/voice-design-complete"
OUTPUT = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-voice-finalists")
TEXT = (
    "Hallo, ich bin Velora. Schön, dass du da bist. "
    "Womit möchtest du heute anfangen?"
)
COMMON = (
    "Eine deutsche Muttersprachlerin aus Deutschland. Sie spricht akzentfreies, "
    "neutrales Standardhochdeutsch mit natürlicher deutscher Satzmelodie. "
    "Keine fremdsprachige, schweizerische oder österreichische Färbung. "
)
PROFILES = {
    "04a_tief_ruhig": COMMON
    + "Erwachsene Frauenstimme mit etwas tieferer Tonlage, ruhig, geerdet, warm und souverän.",
    "04b_tief_sanft": COMMON
    + "Erwachsene Frauenstimme mit tiefer, weicher Klangfarbe; gelassen, nahbar und vertrauenswürdig.",
    "05a_modern_klar": COMMON
    + "Moderne weibliche Assistenzstimme, intelligent, klar und subtil warm; natürlich und niemals werblich.",
    "05b_modern_menschlich": COMMON
    + "Moderne erwachsene Frauenstimme, aufmerksam und menschlich, mit präziser Artikulation und ruhigem Tempo.",
    "06a_reif_warm": COMMON
    + "Reife Frauenstimme mit voller, warmer Klangfarbe; geduldig, beruhigend und natürlich.",
    "06b_reif_elegant": COMMON
    + "Reife, elegante Frauenstimme mit weichem Timbre; freundlich, souverän und unaufdringlich.",
    "07a_neutral_klar": COMMON
    + "Neutrale erwachsene Frauenstimme, ausgewogene Tonhöhe, sehr verständlich und natürlich im Gespräch.",
    "07b_neutral_warm": COMMON
    + "Klare neutrale Frauenstimme mit einem Hauch Wärme; sachlich, entspannt und sympathisch.",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    for name, instruction in PROFILES.items():
        print(f"Generating {name}", flush=True)
        wavs, sample_rate = model.generate_voice_design(
            text=TEXT,
            language="German",
            instruct=instruction,
            max_new_tokens=768,
        )
        sf.write(OUTPUT / f"{name}.wav", wavs[0], sample_rate)


if __name__ == "__main__":
    main()
