"""Build a separately weighted feature set from reviewed real-room clips."""

from __future__ import annotations

import argparse
import random
from pathlib import Path


def repeated_paths(directory: Path, repetitions: int) -> list[str]:
    clips = sorted(directory.glob("*.wav"))
    if not clips:
        raise ValueError(f"No WAV clips found in {directory}")
    return [str(clip) for clip in clips for _ in range(repetitions)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--positive-repetitions", type=int, default=100)
    parser.add_argument("--negative-repetitions", type=int, default=1000)
    parser.add_argument(
        "--labels",
        nargs="+",
        choices=("positive", "negative"),
        default=("positive", "negative"),
    )
    parser.add_argument("--background", type=Path, required=True)
    parser.add_argument("--rir", type=Path, required=True)
    arguments = parser.parse_args()

    import numpy as np
    from run_openwakeword_training import patch_speechbrain_convolution

    random.seed(20260808)
    np.random.seed(20260808)
    import torch

    torch.manual_seed(20260808)
    patch_speechbrain_convolution()
    from openwakeword.data import augment_clips
    from openwakeword.utils import compute_features_from_generator

    backgrounds = [str(path) for path in arguments.background.iterdir() if path.is_file()]
    rirs = [str(path) for path in arguments.rir.iterdir() if path.is_file()]
    probabilities = {
        "SevenBandParametricEQ": 0.15,
        "TanhDistortion": 0.10,
        "PitchShift": 0.15,
        "BandStopFilter": 0.10,
        "AddColoredNoise": 0.15,
        "AddBackgroundNoise": 0.35,
        "Gain": 1.0,
        "RIR": 0.25,
    }
    arguments.output.mkdir(parents=True, exist_ok=True)
    repetitions_by_label = {
        "positive": arguments.positive_repetitions,
        "negative": arguments.negative_repetitions,
    }
    settings = ((label, repetitions_by_label[label]) for label in arguments.labels)
    for label, repetitions in settings:
        paths = repeated_paths(arguments.session / "split" / "train" / label, repetitions)
        generator = augment_clips(
            paths,
            total_length=32_000,
            batch_size=16,
            augmentation_probabilities=probabilities,
            background_clip_paths=backgrounds,
            RIR_paths=rirs,
        )
        compute_features_from_generator(
            generator,
            n_total=len(paths),
            clip_duration=32_000,
            output_file=str(arguments.output / f"real_{label}_features.npy"),
            device="gpu" if torch.cuda.is_available() else "cpu",
            ncpu=1,
        )
        print(f"{label}={len(paths)}")


if __name__ == "__main__":
    main()
