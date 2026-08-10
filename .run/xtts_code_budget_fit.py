"""Fit a generous XTTS emergency code cap from clean non-short measurements."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

RATE = 24_000
CODE_SAMPLES = 1024


def ceil20(value: float) -> int:
    return int(math.ceil(value / 20) * 20)


def features(text: str) -> tuple[int, int]:
    return len("".join(re.findall(r"[\w]", text, flags=re.UNICODE))), len(re.findall(r"[.!?;:]", text))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("/mnt/e/Kyrion/Data/voice-training/xtts-v2-velora-benchmark/results-chunk-20.json"))
    parser.add_argument("--output", type=Path, default=Path("/mnt/e/Kyrion/Data/voice-training/xtts-v2-code-budget-fit.json"))
    args = parser.parse_args()
    data = json.loads(args.source.read_text(encoding="utf-8"))
    raw = []
    for run in data["runs"]:
        if run["textId"] == "short-de":
            continue
        chars, breaks = features(run["text"])
        codes = math.ceil(run["audioDurationSeconds"] * RATE / CODE_SAMPLES)
        raw.append({"textId": run["textId"], "chars": chars, "breaks": breaks, "codes": codes})
    medians = {text_id: float(np.median([row["codes"] for row in raw if row["textId"] == text_id])) for text_id in {row["textId"] for row in raw}}
    # Remove only gross non-terminating outliers; retain ordinary run variation.
    rows = [row for row in raw if row["codes"] <= 1.25 * medians[row["textId"]]]
    x = np.asarray([[1, row["chars"], row["breaks"]] for row in rows], dtype=float)
    y = np.asarray([row["codes"] for row in rows], dtype=float)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = max(0.0, float(np.max(y - x @ beta)))

    def budget(chars: int, breaks: int) -> int:
        return ceil20(1.50 * (beta[0] + beta[1] * chars + beta[2] * breaks) + residual)

    for row in rows:
        row["budget"] = budget(row["chars"], row["breaks"])
        row["usageFraction"] = round(row["codes"] / row["budget"], 6)
    short_chars, short_breaks = features("Ich bin Velora.")
    result = {
        "purpose": "generous emergency brake only; never a semantic completion signal",
        "source": str(args.source),
        "fitRows": len(rows),
        "excludedGrossOutliers": [row for row in raw if row not in rows],
        "features": ["normalized alphanumeric characters", "punctuation breaks"],
        "coefficients": {"intercept": beta[0], "characters": beta[1], "punctuationBreaks": beta[2]},
        "largestPositiveFitResidual": residual,
        "reserveMultiplier": 1.50,
        "formula": "ceil_to_20(1.50 * (40.962 + 1.520 * chars + 7.642 * punctuation_breaks) + 41.737)",
        "rows": rows,
        "observedUsageMax": max(row["usageFraction"] for row in rows),
        "shortExample": {"codes": budget(short_chars, short_breaks), "maximumNominalSeconds": round(budget(short_chars, short_breaks) * CODE_SAMPLES / RATE, 6)},
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
