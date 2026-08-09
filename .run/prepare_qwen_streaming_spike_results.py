"""Aggregate the warm Qwen streaming spike and prepare listening files."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path


TEXTS = ("short", "medium", "long")
WINDOWS = (5, 10, 15, 20, 25)


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for run in summary["runs"]:
        grouped[(run["textId"], run["windowFrames"])].append(run)

    aggregates = []
    for text_id in TEXTS:
        listen = root / "listening" / text_id
        listen.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            root / text_id / "window-5" / "run-1" / "full-decode.wav",
            listen / "full-decode.wav",
        )
        for window in WINDOWS:
            runs = grouped[(text_id, window)]
            shutil.copyfile(
                root / text_id / f"window-{window}" / "run-1" / "streaming.wav",
                listen / f"streaming-{window}-frames.wav",
            )
            aggregates.append(
                {
                    "textId": text_id,
                    "windowFrames": window,
                    "firstCodecFrameMeanMs": mean(
                        [run["firstCodecFrameMs"] for run in runs]
                    ),
                    "firstPlayablePcmMeanMs": mean(
                        [run["firstPlayablePcmMs"] for run in runs]
                    ),
                    "firstPlayablePcmMinMs": min(
                        run["firstPlayablePcmMs"] for run in runs
                    ),
                    "generationCompleteMeanMs": mean(
                        [run["generationCompleteMs"] for run in runs]
                    ),
                    "rtfMean": mean([run["rtf"] for run in runs]),
                    "vramPeakMiB": max(
                        run["memory"]["peakAllocatedMiB"] for run in runs
                    ),
                    "reservedVramMaxMiB": max(
                        run["memory"]["reservedMiB"] for run in runs
                    ),
                    "ramPeakMiB": max(
                        run["memory"]["processPeakRssMiB"] for run in runs
                    ),
                    "lengthDeltaSamples": sorted(
                        {run["quality"]["lengthDeltaSamples"] for run in runs}
                    ),
                    "alignedRmseMean": mean(
                        [run["quality"]["alignedRmse"] for run in runs]
                    ),
                    "maxBoundaryJump": max(
                        run["quality"]["maxBoundaryJump"] for run in runs
                    ),
                }
            )

    cancellations = summary["cancellations"]
    cancellation_groups: dict[int, list[dict]] = defaultdict(list)
    for item in cancellations:
        cancellation_groups[item["cancelAfterMs"]].append(item)
    cancellation_aggregates = [
        {
            "cancelAfterMs": delay,
            "successes": sum(item["cancelCaught"] for item in items),
            "runs": len(items),
            "cancelToStopMeanMs": mean(
                [item["cancelToStopMs"] for item in items]
            ),
            "cancelToStopMaxMs": max(item["cancelToStopMs"] for item in items),
            "allocatedAfterMinMiB": min(
                item["memoryAfterCancellation"]["allocatedMiB"] for item in items
            ),
            "allocatedAfterMaxMiB": max(
                item["memoryAfterCancellation"]["allocatedMiB"] for item in items
            ),
            "reservedAfterMinMiB": min(
                item["memoryAfterCancellation"]["reservedMiB"] for item in items
            ),
            "reservedAfterMaxMiB": max(
                item["memoryAfterCancellation"]["reservedMiB"] for item in items
            ),
        }
        for delay, items in sorted(cancellation_groups.items())
    ]
    target = {
        "source": "summary.json",
        "warmRunsPerConfiguration": 3,
        "aggregates": aggregates,
        "cancellationAggregates": cancellation_aggregates,
    }
    (root / "aggregate.json").write_text(
        json.dumps(target, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
