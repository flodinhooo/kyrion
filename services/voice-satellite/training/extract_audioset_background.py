"""Extract bounded 16 kHz mono background clips from an AudioSet parquet shard."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
import pyarrow.parquet as parquet
import soundfile
from scipy.signal import resample_poly


def _safe_name(value: str, index: int) -> str:
    cleaned = "".join(character for character in value if character.isalnum() or character in "-_")
    return cleaned or f"clip-{index:05d}"


def extract_background(source: Path, output: Path, limit: int) -> int:
    if not source.is_file():
        raise ValueError(f"AudioSet parquet shard does not exist: {source}")
    if limit < 1:
        raise ValueError("Clip limit must be positive")

    output.mkdir(parents=True, exist_ok=True)
    written = 0
    parquet_file = parquet.ParquetFile(source)
    for batch in parquet_file.iter_batches(columns=["video_id", "audio"], batch_size=64):
        for row in batch.to_pylist():
            audio = row["audio"]
            if not audio or not audio.get("bytes"):
                continue
            samples, sample_rate = soundfile.read(
                io.BytesIO(audio["bytes"]), dtype="float32", always_2d=True
            )
            mono = samples.mean(axis=1)
            if sample_rate != 16_000:
                divisor = int(np.gcd(sample_rate, 16_000))
                mono = resample_poly(mono, 16_000 // divisor, sample_rate // divisor)
            name = _safe_name(str(row["video_id"]), written)
            soundfile.write(output / f"{name}.wav", mono, 16_000, subtype="PCM_16")
            written += 1
            if written >= limit:
                return written
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--limit", type=int, default=2_000)
    args = parser.parse_args()
    count = extract_background(args.source, args.output, args.limit)
    print(f"extracted_background_clips={count}")


if __name__ == "__main__":
    main()
