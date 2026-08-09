"""Aggregate and prepare the isolated Qwen boundary-optimization spike."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads((args.root / "summary.json").read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for run in summary["runs"]:
        grouped[run["strategy"]["name"]].append(run)

    aggregates = []
    listening = args.root / "listening"
    listening.mkdir(exist_ok=True)
    first = next(iter(grouped.values()))[0]
    source = args.root / first["strategy"]["name"] / "run-1" / "full-decode.wav"
    shutil.copyfile(source, listening / "00-full-decode.wav")
    for index, (name, runs) in enumerate(grouped.items(), start=1):
        shutil.copyfile(
            args.root / name / "run-1" / "streaming.wav",
            listening / f"{index:02d}-{name}.wav",
        )
        aggregates.append(
            {
                "strategy": name,
                "initialFrames": runs[0]["strategy"]["initial_frames"],
                "strideFrames": runs[0]["strategy"]["stride_frames"],
                "contextFrames": runs[0]["strategy"]["overlap_frames"],
                "crossfadeMs": runs[0]["strategy"]["crossfade_ms"],
                "firstPlayablePcmMeanMs": mean([r["firstPlayablePcmMs"] for r in runs]),
                "firstPlayablePcmMinMs": min(r["firstPlayablePcmMs"] for r in runs),
                "firstPlayablePcmMaxMs": max(r["firstPlayablePcmMs"] for r in runs),
                "generationCompleteMeanMs": mean([r["generationCompleteMs"] for r in runs]),
                "decodeCountMean": mean([r["decodeCount"] for r in runs]),
                "alignedRmseMean": mean([r["quality"]["alignedRmse"] for r in runs]),
                "maxBoundaryJump": max(r["quality"]["maxBoundaryJump"] for r in runs),
                "lengthDeltas": sorted({r["quality"]["lengthDeltaSamples"] for r in runs}),
                "peakAllocatedVramMiB": max(r["memory"]["peakAllocatedMiB"] for r in runs),
            }
        )
    (args.root / "aggregate.json").write_text(
        json.dumps({"warmRunsPerStrategy": 3, "text": "long", "aggregates": aggregates}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
