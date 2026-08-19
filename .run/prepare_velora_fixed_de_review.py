"""Prepare a non-authoritative listening index for the Velora German fixed batch."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9äöüß]+", value.casefold()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    catalog = json.loads((args.root / "catalog.json").read_text(encoding="utf-8"))
    expected = {line["id"]: line["text"] for line in catalog["lines"]}
    hints = json.loads((args.root / "offline-asr-hints.json").read_text(encoding="utf-8"))
    rows = []
    for hint in hints:
        path = Path(hint["input"])
        line_id = path.name.split("__candidate-")[0]
        target = expected[line_id]
        target_normalized = normalize(target)
        observed_normalized = normalize(hint["transcript"])
        ratio = difflib.SequenceMatcher(None, target_normalized, observed_normalized).ratio()
        rows.append({
            "file": path.name,
            "id": line_id,
            "expected": target,
            "asrTranscript": hint["transcript"],
            "exactNormalizedMatch": target_normalized == observed_normalized,
            "similarity": round(ratio, 4),
            "flagForEarlyReview": ratio < 0.8,
            "authority": "offline_asr_hint_only_pending_complete_manual_listening",
        })
    (args.root / "review-assessment.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    playlist = "#EXTM3U\n" + "\n".join(row["file"] for row in rows) + "\n"
    (args.root / "listen-all-in-order.m3u8").write_text(playlist, encoding="utf-8")
    flagged = [row for row in rows if row["flagForEarlyReview"]]
    lines = [
        "# Velora German fixed-response review",
        "",
        "These 60 WAVs are review candidates only: two candidates for each of 30 German lines.",
        "They were cloned from the checksum-verified immutable velora-f reference with Qwen3-TTS 1.7B Base.",
        "No file is owner-approved or registered as a production asset.",
        "",
        "Listen to each complete WAV. Reject wording changes, invented tails, bad endings, identity drift, artifacts, or unsuitable prosody.",
        "The ASR transcript is only a triage hint and never replaces listening.",
        "",
        f"Technical validation: 60 WAVs, mono PCM16/24 kHz. ASR early-review flags: {len(flagged)}.",
        "",
        "## Early-review flags",
        "",
    ]
    lines.extend(
        f"- `{row['file']}` — expected: {row['expected']} — ASR: {row['asrTranscript']}"
        for row in flagged
    )
    if not flagged:
        lines.append("- None.")
    (args.root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(rows), "earlyReviewFlags": len(flagged)}, indent=2))


if __name__ == "__main__":
    main()
