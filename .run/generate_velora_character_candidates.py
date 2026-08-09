from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


MODEL = "/training/models/qwen3-tts/voice-design-complete"
OUTPUT = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-character-candidates")
TEXT = (
    "Guten Abend. Ich bin Velora. Das Licht im Wohnzimmer ist noch eingeschaltet. "
    "Soll ich es dimmen, oder möchtest du den Raum lieber genauso lassen?"
)
BASE = (
    "Eine deutsche Muttersprachlerin spricht natürliches, akzentfreies Standardhochdeutsch. "
    "Erwachsene weibliche Stimme mit warmer, eher mitteltiefer Klangfarbe und flüssiger, "
    "menschlicher Satzmelodie. Die Stimme beginnt bereits auf der ersten Silbe ruhig in ihrer "
    "normalen mitteltiefen Lage, ohne hohen Toneinsatz und ohne nach oben zu springen. "
    "Keine hauchige oder verführerische Werbestimme, kein Synchron- oder Übersetzungsrhythmus, "
    "keine Nachrichtensprecherin und keine sterile Roboterstimme. "
)
CANDIDATES = {
    "A_ruhige_praesenz": BASE
    + "Sie wirkt gelassen, aufmerksam und souverän. Kleine natürliche Betonungen geben ihr Persönlichkeit, ohne theatralisch zu werden.",
    "B_warme_praezision": BASE
    + "Sie verbindet ruhige Präzision mit ehrlicher Wärme. Ihre Stimme ist klar, charaktervoll und im Gespräch angenehm direkt.",
    "C_trockener_charme": BASE
    + "Sie besitzt subtilen trockenen Charme und eine leicht markante Klangfarbe. Freundlich, intelligent und niemals übertrieben fröhlich.",
    "D_vertraute_begleiterin": BASE
    + "Sie klingt wie eine vertraute, kompetente Begleiterin: ruhig, nahbar und individuell, mit feinen emotionalen Nuancen statt künstlicher Glätte.",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    for name, instruction in CANDIDATES.items():
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
