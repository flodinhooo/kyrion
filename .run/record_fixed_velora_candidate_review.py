"""Record the owner's listening review without modifying or registering WAVs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FAILURES = {
    ("de", "session.greeting", "neutral-01"): "Fantasy speech at the ending.",
    ("de", "session.greeting", "warm-01"): "Significant fantasy speech at the ending, worse than neutral.",
    ("de", "session.farewell", "neutral-01"): "German farewell contains fantasy words.",
    ("de", "session.farewell", "warm-01"): "German farewell contains fantasy words.",
    ("de", "dialogue.acknowledged", "neutral-01"): "Punctuation is audibly spoken as 'Punkt'.",
    ("de", "dialogue.acknowledged", "neutral-02"): "Punctuation is audibly spoken as 'Punkt'.",
    ("en", "session.greeting", "neutral-01"): "Fantasy speech at the ending.",
    ("en", "session.farewell", "warm-01"): "Unnatural tone at the ending.",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.results.read_text(encoding="utf-8"))
    reviewed = 0
    for asset in payload["assets"]:
        key = (asset["locale"], asset["responseKey"], asset["variantId"])
        if key not in FAILURES:
            continue
        asset["classification"] = "manual_fail"
        asset["manualReview"] = {
            "reviewer": "owner",
            "status": "complete",
            "decision": "fail",
            "reason": FAILURES[key],
        }
        reviewed += 1
    payload["status"] = "manual_review_in_progress"
    payload["registered"] = False
    payload["productionAssets"] = False
    payload["reviewSummary"] = {
        "failed": reviewed,
        "pending": len(payload["assets"]) - reviewed,
        "accepted": 0,
        "note": "No candidate may be registered until explicitly accepted by the owner.",
    }
    args.results.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"recorded_failed={reviewed} pending={len(payload['assets']) - reviewed}")


if __name__ == "__main__":
    main()
