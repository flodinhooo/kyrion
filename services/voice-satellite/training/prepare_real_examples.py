"""Prepare reviewed real-room clips for training without leaking the holdout set."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


def is_holdout(clip_number: int) -> bool:
    """Select a deterministic cross-section across the recording order."""
    return clip_number % 5 == 2


def prepare(session: Path, model_output: Path) -> dict[str, int]:
    with (session / "manifest.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    counts = {"positive_train": 0, "positive_test": 0, "negative_train": 0, "negative_test": 0}
    for row in rows:
        label = row["label"]
        if label not in {"positive", "negative"}:
            continue
        clip_number = int(Path(row["file"]).stem.split("-")[-1])
        split = "test" if is_holdout(clip_number) else "train"
        key = f"{label}_{split}"
        counts[key] += 1
        source = session / label / row["file"]

        private_target = session / "split" / split / label / row["file"]
        private_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, private_target)

        if split == "train":
            replicas = 20 if label == "positive" else 200
            destination = model_output / f"{label}_train"
            destination.mkdir(parents=True, exist_ok=True)
            for replica in range(replicas):
                name = f"real-20260808-{Path(row['file']).stem}-r{replica:03d}.wav"
                shutil.copy2(source, destination / name)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("model_output", type=Path)
    arguments = parser.parse_args()
    counts = prepare(arguments.session, arguments.model_output)
    print(", ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
