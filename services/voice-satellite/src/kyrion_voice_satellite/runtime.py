from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from typing import Protocol

LOGGER = logging.getLogger("kyrion-voice-satellite")


class WakeWordDetector(Protocol):
    def score(self, frame: bytes) -> float: ...


def listen(
    frames: Iterable[bytes],
    detector: WakeWordDetector,
    threshold: float,
    cooldown_seconds: float,
    on_detected: Callable[[float], None],
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    next_allowed_at = 0.0
    for frame in frames:
        score = detector.score(frame)
        now = monotonic()
        if score < threshold or now < next_allowed_at:
            continue
        next_allowed_at = now + cooldown_seconds
        on_detected(score)


def wait_for_detection(
    frames: Iterable[bytes], detector: WakeWordDetector, threshold: float
) -> float:
    """Return on the first wake event so the capture generator can be closed."""
    for frame in frames:
        score = detector.score(frame)
        if score >= threshold:
            return score
    raise RuntimeError("Audio capture ended before wake detection")


def log_detection(score: float) -> None:
    LOGGER.info("Wake word detected (score=%.3f)", score)
