"""Normalize generated wake-word WAV files to the training audio contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile
from scipy.signal import resample_poly


def normalize_tree(root: Path) -> tuple[int, int]:
    checked = 0
    normalized = 0
    for path in root.glob("**/*.wav"):
        info = soundfile.info(path)
        checked += 1
        if info.samplerate == 16_000 and info.channels == 1 and info.subtype == "PCM_16":
            continue
        samples, sample_rate = soundfile.read(path, dtype="float32", always_2d=True)
        mono = samples.mean(axis=1)
        if sample_rate != 16_000:
            divisor = int(np.gcd(sample_rate, 16_000))
            mono = resample_poly(mono, 16_000 // divisor, sample_rate // divisor)
        temporary = path.with_suffix(".normalized.wav")
        soundfile.write(temporary, mono, 16_000, subtype="PCM_16")
        temporary.replace(path)
        normalized += 1
    return checked, normalized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    checked, normalized = normalize_tree(args.root)
    print(f"checked={checked} normalized={normalized}")


if __name__ == "__main__":
    main()
