"""Build a review playlist and validate generated gratitude WAVs."""

from __future__ import annotations

import json
import wave
from pathlib import Path

ROOT = Path("E:/Kyrion/Data/voice-production/velora-gratitude-de-v1/review-candidates")


def main() -> None:
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    expected = {line["id"]: line["text"] for line in catalog["lines"]}
    paths = sorted(ROOT.glob("*.wav"))
    if len(paths) != len(expected) * 2:
        raise RuntimeError("Candidate inventory is incomplete")
    rows = []
    for path in paths:
        line_id = path.name.split("__candidate-")[0]
        with wave.open(str(path), "rb") as audio:
            audio_format = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
            if audio_format != (1, 2, 24_000):
                raise RuntimeError(f"Invalid WAV format: {path}")
            rows.append({
                "file": path.name,
                "text": expected[line_id],
                "durationSeconds": round(audio.getnframes() / audio.getframerate(), 3),
                "status": "review_only_pending_owner_listening",
            })
    (ROOT / "review-index.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "listen-all-in-order.m3u8").write_text(
        "#EXTM3U\n" + "\n".join(row["file"] for row in rows) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidates": len(rows), "allWavFormatsValid": True}))


if __name__ == "__main__":
    main()
