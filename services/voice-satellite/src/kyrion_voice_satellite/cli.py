from __future__ import annotations

import argparse
import logging
from pathlib import Path

from kyrion_voice_satellite.audio import AlsaCapture
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.detector import OpenWakeWordDetector
from kyrion_voice_satellite.runtime import listen, log_detection


def main() -> None:
    parser = argparse.ArgumentParser(description="Kyrion voice satellite")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = SatelliteConfig.load(args.config)
    detector = OpenWakeWordDetector(config.model_path)
    listen(
        AlsaCapture(config.capture_device).frames(), detector, config.threshold,
        config.cooldown_seconds, log_detection,
    )


if __name__ == "__main__":
    main()
