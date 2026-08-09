"""Score reviewed 16 kHz PCM16 clips with one openWakeWord ONNX model."""

from __future__ import annotations

import argparse
import csv
import wave
from pathlib import Path

FRAME_SAMPLES = 1_280


def load_samples(path: Path):
    import numpy as np

    with wave.open(str(path), "rb") as stream:
        if (
            stream.getnchannels() != 1
            or stream.getsampwidth() != 2
            or stream.getframerate() != 16_000
        ):
            raise ValueError(f"Expected 16 kHz mono PCM16 WAV input: {path}")
        samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype=np.int16)
    padding = np.zeros(16_000, dtype=np.int16)
    return np.concatenate((padding, samples, padding))


def score_clip(model_path: Path, clip_path: Path) -> float:
    import numpy as np
    from openwakeword.model import Model

    model = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
    samples = load_samples(clip_path)
    scores = []
    for start in range(0, len(samples), FRAME_SAMPLES):
        frame = samples[start : start + FRAME_SAMPLES]
        if len(frame) < FRAME_SAMPLES:
            frame = np.pad(frame, (0, FRAME_SAMPLES - len(frame)))
        scores.extend(float(value) for value in model.predict(frame).values())
    return max(scores, default=0.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("clips", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    results = [
        (clip.name, score_clip(arguments.model, clip))
        for clip in sorted(arguments.clips.glob("*.wav"))
    ]
    if not results:
        raise ValueError(f"No WAV clips found in {arguments.clips}")
    for name, score in results:
        print(f"{name},{score:.6f}")
    print(f"count={len(results)}, min={min(score for _, score in results):.6f}, "
          f"max={max(score for _, score in results):.6f}")

    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        with arguments.output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("file", "score"))
            writer.writerows((name, f"{score:.6f}") for name, score in results)


if __name__ == "__main__":
    main()
