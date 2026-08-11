"""Record the owner's authoritative Stage-1 Short-TTS listening decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REVIEW = {
    "reviewer": "owner",
    "reviewedAllWavs": True,
    "decision": "fail",
    "candidateDecision": "C",
    "stage2Eligible": False,
    "reasonCode": "VOICE_QUALITY_OR_IDENTITY_UNACCEPTABLE",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    summary: dict[str, object] = {
        "status": "complete",
        "acceptedShortTtsProvider": None,
        "reviewer": "owner",
        "providers": {},
    }
    reasons = {
        "piper": (
            "Extremely fast, but audio quality and voice identity are not remotely "
            "acceptable for Velora."
        ),
        "chatterbox": (
            "Audio quality and Velora suitability are not acceptable; batch latency is "
            "also unacceptable for the Short path."
        ),
    }
    for provider in ("piper", "chatterbox"):
        target = args.root / provider / "stage-1/results.json"
        data = json.loads(target.read_text(encoding="utf-8"))
        provider_review = {**REVIEW, "reason": reasons[provider]}
        data["manualReviewStatus"] = "complete"
        data["manualReview"] = provider_review
        data["candidateDecision"] = "C"
        data["stage2Eligible"] = False
        for run in data["runs"]:
            run["classification"] = "manual_fail_voice_quality_or_identity"
            run["review"] = {
                "reviewer": "owner",
                "status": "complete",
                "candidateLevelDecision": "fail",
                "note": reasons[provider],
            }
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["providers"][provider] = provider_review
        print(f"recorded {provider}: C / stage2Eligible=false")
    (args.root / "stage-1-manual-review.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
