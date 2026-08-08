"""Combine and deterministically shuffle two openWakeWord feature arrays."""

from __future__ import annotations

import argparse
import random
from pathlib import Path


def shuffled_sources(
    primary_count: int, secondary_count: int, repeat: int
) -> list[tuple[int, int]]:
    sources = [(0, index) for index in range(primary_count)]
    sources.extend((1, index) for _ in range(repeat) for index in range(secondary_count))
    random.Random(20260808).shuffle(sources)
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("primary", type=Path)
    parser.add_argument("secondary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--secondary-repeat", type=int, default=4)
    arguments = parser.parse_args()

    import numpy as np
    from numpy.lib.format import open_memmap

    primary = np.load(arguments.primary, mmap_mode="r")
    secondary = np.load(arguments.secondary, mmap_mode="r")
    if primary.shape[1:] != secondary.shape[1:]:
        raise ValueError(f"Feature shapes differ: {primary.shape} != {secondary.shape}")
    sources = shuffled_sources(len(primary), len(secondary), arguments.secondary_repeat)
    output = open_memmap(
        arguments.output,
        mode="w+",
        dtype=np.float32,
        shape=(len(sources), *primary.shape[1:]),
    )
    for destination, (source, index) in enumerate(sources):
        output[destination] = primary[index] if source == 0 else secondary[index]
    output.flush()
    print(f"combined_shape={output.shape}")


if __name__ == "__main__":
    main()
