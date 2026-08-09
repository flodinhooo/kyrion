from __future__ import annotations

import argparse
import logging
from pathlib import Path

from kyrion_voice_satellite.audio import AlsaCapture
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.detector import OpenWakeWordDetector
from kyrion_voice_satellite.dialogue import DialogueRunner
from kyrion_voice_satellite.runtime import listen, log_detection, wait_for_detection


def main() -> None:
    parser = argparse.ArgumentParser(description="Kyrion voice satellite")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = SatelliteConfig.load(args.config)
    dialogue = DialogueRunner(config) if config.dialogue_enabled else None

    if dialogue is not None:
        while True:
            # Closing this generator terminates arecord before dialogue capture starts.
            frames = AlsaCapture(config.capture_device).frames()
            try:
                score = wait_for_detection(
                    frames, OpenWakeWordDetector(config.model_path), config.threshold
                )
            finally:
                frames.close()
            log_detection(score)
            dialogue.run_session()

    detector = OpenWakeWordDetector(config.model_path)

    def detected(score: float) -> None:
        log_detection(score)
    listen(
        AlsaCapture(config.capture_device).frames(), detector, config.threshold,
        config.cooldown_seconds, detected,
    )


if __name__ == "__main__":
    main()
