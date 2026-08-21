"""Validate and index the generated Velora expansion without approving assets."""

from __future__ import annotations

import json
import urllib.request
import wave
from pathlib import Path

ROOT = Path("E:/Kyrion/Data/voice-production/velora-expansion-de-v1/review-candidates")


def transcribe(path: Path) -> str:
    request = urllib.request.Request(
        "http://127.0.0.1:8000/v1/speech/transcribe",
        data=path.read_bytes(),
        headers={"Content-Type": "audio/wav", "X-Kyrion-Locale": "de"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["text"]


def main() -> None:
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    expected = {line["id"]: line["text"] for line in catalog["lines"]}
    rows = []
    for path in sorted(ROOT.glob("*.wav")):
        line_id = path.name.split("__candidate-")[0]
        with wave.open(str(path), "rb") as wav_file:
            row = {
                "file": path.name,
                "id": line_id,
                "expected": expected[line_id],
                "channels": wav_file.getnchannels(),
                "sampleWidthBytes": wav_file.getsampwidth(),
                "sampleRateHz": wav_file.getframerate(),
                "durationSeconds": round(wav_file.getnframes() / wav_file.getframerate(), 3),
                "asrHint": transcribe(path),
                "status": "review_only_pending_owner_listening",
            }
        if (row["channels"], row["sampleWidthBytes"], row["sampleRateHz"]) != (1, 2, 24_000):
            raise RuntimeError(f"Invalid WAV format: {path}")
        rows.append(row)
    if len(rows) != len(expected) * catalog["candidatesPerLine"]:
        raise RuntimeError("Candidate inventory is incomplete")
    (ROOT / "review-index.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "listen-all-in-order.m3u8").write_text(
        "#EXTM3U\n" + "\n".join(row["file"] for row in rows) + "\n", encoding="utf-8"
    )
    summary = [
        "# Velora voice expansion review",
        "",
        "These files are generated review candidates, not production assets.",
        "Listen to every complete WAV and select or reject each candidate.",
        "ASR text is a diagnostic hint only and never constitutes approval.",
        "",
        "| File | Expected | Parakeet hint | Duration |",
        "| --- | --- | --- | ---: |",
    ]
    summary.extend(
        f"| `{row['file']}` | {row['expected']} | {row['asrHint']} | {row['durationSeconds']:.3f} s |"
        for row in rows
    )
    (ROOT / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(rows), "allWavFormatsValid": True}, indent=2))


if __name__ == "__main__":
    main()
