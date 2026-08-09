"""Normalise provider samples and create a deterministic blind comparison."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
from pathlib import Path


TEXT_IDS = ("short", "medium", "long")
PROVIDERS = ("qwen-1.7b-f", "qwen-0.6b-f", "chatterbox-f")


def normalise(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            "loudnorm=I=-20:LRA=7:TP=-2",
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root
    comparison = root / "comparison"
    blind = root / "blind"
    mapping: dict[str, str] = {}
    rng = random.Random(20260809)

    for text_id in TEXT_IDS:
        prepared = []
        for provider in PROVIDERS:
            source = root / "raw" / provider / f"{text_id}.wav"
            target = comparison / text_id / f"{provider}.wav"
            normalise(source, target)
            prepared.append((provider, target))
        rng.shuffle(prepared)
        for letter, (provider, source) in zip("abc", prepared, strict=True):
            name = f"{text_id}-{letter}.wav"
            blind.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, blind / name)
            mapping[name] = provider

    (blind / "mapping.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
