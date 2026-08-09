from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


MODEL = "/training/models/qwen3-tts/voice-design-complete"
OUTPUT = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options")
TEXT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
BASE = (
    "Eine klar und eindeutig weiblich klingende deutsche Muttersprachlerin aus Deutschland. "
    "Natürliches, akzentfreies Standardhochdeutsch mit authentischer deutscher Satzmelodie. "
    "Kein hoher Toneinsatz am Satzanfang, keine männliche oder androgyne Klangfarbe. "
    "Nicht hauchig, nicht verführerisch, nicht werblich, nicht künstlich übersetzt und nicht robotisch. "
)
OPTIONS = {
    "E_weiblich_warm": BASE
    + "Warme weibliche Mezzosopranstimme, erwachsen, ruhig und charaktervoll; freundlich ohne übertriebene Fröhlichkeit.",
    "F_weiblich_klar": BASE
    + "Klare moderne Frauenstimme mit natürlicher mittlerer Tonlage, präzise, intelligent und lebendig.",
    "G_weiblich_tief": BASE
    + "Deutlich weibliche Altstimme mit warmer tiefer Klangfarbe, souverän, gelassen und weich, aber nicht dunkel-männlich.",
    "H_weiblich_sanft": BASE
    + "Sanfte erwachsene Frauenstimme, nahbar und emotional fein, mit natürlichem Atem und ruhigem Sprachfluss.",
    "I_weiblich_markant": BASE
    + "Markante weibliche Stimme mit eigener heller Textur und subtil trockenem Charme, selbstbewusst und entspannt.",
    "J_weiblich_elegant": BASE
    + "Elegante reife Frauenstimme mit voller weiblicher Resonanz, warmer Präzision und unaufdringlicher Persönlichkeit.",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    for name, instruction in OPTIONS.items():
        print(f"Generating {name}", flush=True)
        wavs, sample_rate = model.generate_voice_design(
            text=TEXT,
            language="German",
            instruct=instruction,
            max_new_tokens=1024,
        )
        sf.write(OUTPUT / f"{name}.wav", wavs[0], sample_rate)


if __name__ == "__main__":
    main()
