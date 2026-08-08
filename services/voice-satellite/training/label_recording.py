"""Apply human-reviewed labels to segmented private wake-word recordings."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


def parse_numbers(value: str) -> set[int]:
    if not value:
        return set()
    return {int(item.strip()) for item in value.split(",")}


def label_recording(directory: Path, negatives: set[int], excluded: set[int]) -> dict[str, int]:
    if negatives & excluded:
        raise ValueError("A clip cannot be both negative and excluded")
    manifest = directory / "manifest.csv"
    with manifest.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    known = {int(Path(row["file"]).stem.split("-")[-1]) for row in rows}
    unknown = (negatives | excluded) - known
    if unknown:
        raise ValueError(f"Unknown clip numbers: {sorted(unknown)}")

    counts = {"positive": 0, "negative": 0, "excluded": 0}
    for row in rows:
        number = int(Path(row["file"]).stem.split("-")[-1])
        if number in excluded:
            label = "excluded"
        elif number in negatives:
            label = "negative"
        else:
            label = "positive"
        row["label"] = label
        counts[label] += 1
        target = directory / label / row["file"]
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(directory / row["file"], target)

    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--negative", default="", help="Comma-separated clip numbers")
    parser.add_argument("--exclude", default="", help="Comma-separated clip numbers")
    arguments = parser.parse_args()
    counts = label_recording(
        arguments.directory,
        parse_numbers(arguments.negative),
        parse_numbers(arguments.exclude),
    )
    print(", ".join(f"{label}={count}" for label, count in counts.items()))


if __name__ == "__main__":
    main()
