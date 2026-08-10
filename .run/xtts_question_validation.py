"""Quality controls for the only punctuation variant that improved Short DE."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from faster_whisper import WhisperModel
from TTS.api import TTS

BASE_PATH = Path(__file__).with_name("xtts_short_punctuation_matrix.py")
SPEC = importlib.util.spec_from_file_location("punctuation", BASE_PATH)
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

TEXTS = {
    "medium-de": ("de", "Ich bin Velora und begleite dich durch deinen Alltag."),
    "long-de": ("de", "Natürlich, Flo. Ich helfe dir dabei, den Überblick zu behalten und die nächsten Schritte in Ruhe zu planen. Sag mir einfach, womit wir beginnen sollen."),
    "dialogue-de": ("de", "Ja, Madrid ist die Hauptstadt Spaniens. Barcelona ist ebenfalls sehr bedeutend, aber Madrid wurde zum politischen und administrativen Zentrum des Landes."),
    "numbers-de": ("de", "Heute sind es 21,5 Grad. Der Termin beginnt um 14:35 Uhr."),
    "numbers-en": ("en", "It is 21.5 degrees. Your appointment starts at 2:35 p.m."),
    "domain-de": ("de", "Velora, schalte bitte die desk lamp im Gamingraum ein."),
    "domain-en": ("en", "Velora, turn on the desk lamp in the gaming room, please."),
}


def question(text: str) -> str:
    return text.rstrip(".!?; ") + "?"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/mnt/e/Kyrion/Data/voice-training/xtts-v2-question-validation"))
    args = parser.parse_args()
    if hashlib.sha256(base.REFERENCE.read_bytes()).hexdigest() != base.REFERENCE_SHA256:
        raise RuntimeError("reference checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(base.REFERENCE)])
    aligners = {language: WhisperModel("small", device="cpu", compute_type="int8") for language in {"de", "en"}}
    list(model.inference_stream("Systemstart.", "de", *conditioning, stream_chunk_size=base.CHUNK_TOKENS, **base.PARAMETERS))
    original = dict(base.VARIANTS)
    runs = []
    try:
        for index, (text_id, (language, text)) in enumerate(TEXTS.items(), 1):
            transformed = question(text)
            base.VARIANTS[text_id] = transformed
            result = base.run(model, aligners[language], conditioning, text_id, 60_000 + index, args.output, language)
            result.update({"textId": text_id, "language": language, "sourceText": text, "prosodyRisk": "declarative input forced to question terminal"})
            runs.append(result)
    finally:
        base.VARIANTS.clear()
        base.VARIANTS.update(original)
    (args.output / "results.json").write_text(json.dumps({"variant": "replace final terminal with ?", "runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
