"""Transcribe private Phase 3.2 clips for review; writes no audio."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("clips", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    model = WhisperModel("small", device="cpu", compute_type="int8")
    results = []
    for clip in sorted(args.clips.glob("clip-*.wav")):
        clip_number = int(clip.stem.removeprefix("clip-"))
        language = "en" if 13 <= clip_number <= 20 else "de"
        started = time.perf_counter()
        segments, _ = model.transcribe(
            str(clip),
            language=language,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        results.append(
            {"clip": clip.name, "seconds": round(time.perf_counter() - started, 3), "text": text}
        )
        print(f"{clip.name}: {text}")
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
