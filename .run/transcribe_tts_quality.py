"""Final-transcript quality probe for private TTS benchmark WAV files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    results = []
    for path in args.inputs:
        language = "en" if "-en-" in path.name else "de"
        segments, info = model.transcribe(
            str(path),
            language=language,
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        results.append(
            {
                "input": str(path),
                "language": language,
                "languageProbability": round(info.language_probability, 6),
                "transcript": " ".join(
                    segment.text.strip() for segment in segments
                ).strip(),
            }
        )
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
