"""Merge reviewed recording sessions without losing provenance or colliding names."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


def merge(sessions: list[Path], output: Path) -> dict[str, int]:
    rows: list[dict[str, str]] = []
    counts = {"positive": 0, "negative": 0, "excluded": 0}
    output.mkdir(parents=True, exist_ok=True)

    for session in sessions:
        with (session / "manifest.csv").open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                label = row["label"]
                if label not in counts:
                    raise ValueError(f"Unsupported label {label!r} in {session}")
                source = session / label / row["file"]
                name = f"{session.parent.name}-{row['file']}"
                destination = output / label / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                rows.append({**row, "file": name})
                counts[label] += 1

    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("sessions", nargs="+", type=Path)
    arguments = parser.parse_args()
    counts = merge(arguments.sessions, arguments.output)
    print(", ".join(f"{label}={count}" for label, count in counts.items()))


if __name__ == "__main__":
    main()
