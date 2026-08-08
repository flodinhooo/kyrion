"""Split a continuous mono PCM wake-word recording into reviewable clips."""

from __future__ import annotations

import argparse
import csv
import math
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Segment:
    start_frame: int
    end_frame: int


def rms(samples: bytes) -> float:
    values = memoryview(samples).cast("h")
    if not values:
        return 0.0
    return math.sqrt(sum(value * value for value in values) / len(values)) / 32768


def find_segments(
    frame_rms: list[float],
    *,
    frame_seconds: float,
    threshold: float,
    max_gap_seconds: float = 0.45,
    min_speech_seconds: float = 0.18,
) -> list[Segment]:
    active = [index for index, value in enumerate(frame_rms) if value >= threshold]
    if not active:
        return []

    max_gap = max(1, round(max_gap_seconds / frame_seconds))
    minimum = max(1, round(min_speech_seconds / frame_seconds))
    segments: list[Segment] = []
    start = previous = active[0]
    for current in active[1:]:
        if current - previous > max_gap:
            if previous + 1 - start >= minimum:
                segments.append(Segment(start, previous + 1))
            start = current
        previous = current
    if previous + 1 - start >= minimum:
        segments.append(Segment(start, previous + 1))
    return segments


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def segment_recording(source: Path, output: Path) -> int:
    with wave.open(str(source), "rb") as recording:
        if (
            recording.getnchannels() != 1
            or recording.getsampwidth() != 2
            or recording.getframerate() != 16_000
        ):
            raise ValueError("Expected 16 kHz mono PCM16 WAV input")
        parameters = recording.getparams()
        audio = recording.readframes(recording.getnframes())

    samples_per_frame = round(parameters.framerate * 0.02)
    bytes_per_frame = samples_per_frame * parameters.sampwidth
    chunks = [audio[offset : offset + bytes_per_frame] for offset in range(0, len(audio), bytes_per_frame)]
    levels = [rms(chunk) for chunk in chunks if len(chunk) == bytes_per_frame]
    noise_floor = percentile(levels, 0.50)
    threshold = max(0.0012, noise_floor * 3.5)
    segments = find_segments(levels, frame_seconds=0.02, threshold=threshold)

    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["file", "start_seconds", "end_seconds", "duration_seconds", "label"])
        for index, segment in enumerate(segments, start=1):
            # Context helps review and lets augmentation crop each utterance naturally.
            start_sample = max(0, segment.start_frame * samples_per_frame - round(0.25 * parameters.framerate))
            end_sample = min(
                len(audio) // parameters.sampwidth,
                segment.end_frame * samples_per_frame + round(0.35 * parameters.framerate),
            )
            clip_name = f"clip-{index:03d}.wav"
            with wave.open(str(output / clip_name), "wb") as clip:
                clip.setparams(parameters)
                clip.writeframes(
                    audio[start_sample * parameters.sampwidth : end_sample * parameters.sampwidth]
                )
            writer.writerow(
                [
                    clip_name,
                    f"{start_sample / parameters.framerate:.3f}",
                    f"{end_sample / parameters.framerate:.3f}",
                    f"{(end_sample - start_sample) / parameters.framerate:.3f}",
                    "unreviewed",
                ]
            )
    print(f"Created {len(segments)} clips in {output}; threshold={threshold:.6f}")
    return len(segments)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    segment_recording(arguments.source, arguments.output)


if __name__ == "__main__":
    main()
