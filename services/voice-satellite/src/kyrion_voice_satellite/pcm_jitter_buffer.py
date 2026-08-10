from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Condition

from kyrion_voice_satellite.pcm_downlink import FRAME_BYTES, FRAME_MILLISECONDS


class PcmJitterBufferError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PcmJitterBufferMetrics:
    frames_received: int
    frames_consumed: int
    frames_discarded: int
    refill_deadline_misses: int
    backpressure_waits: int
    peak_queued_frames: int
    cancelled: bool


class PcmJitterBuffer:
    """Bounded single-producer PCM queue; it does not own an audio device."""

    def __init__(self, *, capacity_frames: int = 8, prebuffer_frames: int = 2) -> None:
        if capacity_frames < 1:
            raise ValueError("capacity_frames must be positive")
        if prebuffer_frames not in range(1, capacity_frames + 1):
            raise ValueError("prebuffer_frames must fit inside capacity_frames")
        self._capacity = capacity_frames
        self._prebuffer = prebuffer_frames
        self._frames: deque[bytes] = deque()
        self._condition = Condition()
        self._producer_complete = False
        self._cancelled = False
        self._playing = False
        self._received = 0
        self._consumed = 0
        self._discarded = 0
        self._refill_deadline_misses = 0
        self._backpressure_waits = 0
        self._peak = 0

    def push(self, frame: bytes, *, timeout: float = 1.0) -> None:
        if len(frame) != FRAME_BYTES:
            raise PcmJitterBufferError("PCM jitter buffer received an invalid frame")
        deadline = time.monotonic() + timeout
        with self._condition:
            waited = False
            while len(self._frames) >= self._capacity and not self._cancelled:
                if not waited:
                    self._backpressure_waits += 1
                    waited = True
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self._condition.wait(remaining):
                    raise PcmJitterBufferError("PCM jitter buffer backpressure timeout")
            if self._cancelled:
                raise PcmJitterBufferError("PCM jitter buffer is cancelled")
            if self._producer_complete:
                raise PcmJitterBufferError("PCM jitter buffer is complete")
            self._frames.append(frame)
            self._received += 1
            self._peak = max(self._peak, len(self._frames))
            self._condition.notify_all()

    def complete(self) -> None:
        with self._condition:
            self._producer_complete = True
            self._condition.notify_all()

    def cancel(self) -> None:
        with self._condition:
            if not self._cancelled:
                self._cancelled = True
                self._discarded += len(self._frames)
                self._frames.clear()
            self._condition.notify_all()

    def play(self, consume: Callable[[bytes], None]) -> PcmJitterBufferMetrics:
        with self._condition:
            if self._playing:
                raise PcmJitterBufferError("PCM jitter buffer already has a consumer")
            self._playing = True
            while (
                len(self._frames) < self._prebuffer
                and not self._producer_complete
                and not self._cancelled
            ):
                self._condition.wait()

        primed = 0
        while primed < self._prebuffer:
            with self._condition:
                if self._cancelled:
                    return self.metrics()
                if not self._frames:
                    break
                frame = self._frames.popleft()
                self._condition.notify_all()
            consume(frame)
            with self._condition:
                self._consumed += 1
            primed += 1

        next_deadline = time.monotonic() + FRAME_MILLISECONDS / 1_000
        while True:
            remaining = next_deadline - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            with self._condition:
                while not self._frames and not self._producer_complete and not self._cancelled:
                    self._refill_deadline_misses += 1
                    self._condition.wait()
                if self._cancelled:
                    return self.metrics()
                if not self._frames and self._producer_complete:
                    return self.metrics()
                frame = self._frames.popleft()
                self._condition.notify_all()

            consume(frame)
            with self._condition:
                self._consumed += 1
            next_deadline += FRAME_MILLISECONDS / 1_000

    def metrics(self) -> PcmJitterBufferMetrics:
        with self._condition:
            return PcmJitterBufferMetrics(
                frames_received=self._received,
                frames_consumed=self._consumed,
                frames_discarded=self._discarded,
                refill_deadline_misses=self._refill_deadline_misses,
                backpressure_waits=self._backpressure_waits,
                peak_queued_frames=self._peak,
                cancelled=self._cancelled,
            )
