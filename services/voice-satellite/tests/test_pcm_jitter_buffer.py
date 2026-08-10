import time
from threading import Event, Thread

import pytest

from kyrion_voice_satellite.pcm_downlink import FRAME_BYTES
from kyrion_voice_satellite.pcm_jitter_buffer import (
    PcmJitterBuffer,
    PcmJitterBufferError,
)


def frame(value=0):
    return bytes([value]) * FRAME_BYTES


def test_prebuffers_then_consumes_all_frames_in_order():
    buffer = PcmJitterBuffer(capacity_frames=4, prebuffer_frames=2)
    buffer.push(frame(1))
    buffer.push(frame(2))
    buffer.complete()
    consumed = []

    metrics = buffer.play(consumed.append)

    assert consumed == [frame(1), frame(2)]
    assert metrics.frames_received == 2
    assert metrics.frames_consumed == 2
    assert metrics.peak_queued_frames == 2
    assert metrics.refill_deadline_misses == 0


def test_primes_the_downstream_sink_with_the_complete_prebuffer():
    buffer = PcmJitterBuffer(capacity_frames=4, prebuffer_frames=2)
    buffer.push(frame(1))
    buffer.push(frame(2))
    buffer.complete()
    consumed_at = []

    started = time.monotonic()
    buffer.play(lambda _frame: consumed_at.append(time.monotonic() - started))

    assert len(consumed_at) == 2
    assert max(consumed_at) < 0.05


def test_applies_bounded_backpressure_instead_of_growing():
    buffer = PcmJitterBuffer(capacity_frames=2, prebuffer_frames=1)
    buffer.push(frame())
    buffer.push(frame())

    with pytest.raises(PcmJitterBufferError, match="backpressure timeout"):
        buffer.push(frame(), timeout=0)

    metrics = buffer.metrics()
    assert metrics.peak_queued_frames == 2
    assert metrics.backpressure_waits == 1


def test_cancellation_discards_queued_audio_and_stops_consumer():
    buffer = PcmJitterBuffer(capacity_frames=4, prebuffer_frames=3)
    buffer.push(frame(1))
    buffer.push(frame(2))
    consumed = []
    finished = Event()

    thread = Thread(target=lambda: (buffer.play(consumed.append), finished.set()))
    thread.start()
    buffer.cancel()
    thread.join(timeout=1)

    assert finished.is_set()
    assert consumed == []
    assert buffer.metrics().frames_discarded == 2
    assert buffer.metrics().cancelled is True


def test_records_refill_deadline_miss_and_recovers_when_a_late_frame_arrives():
    buffer = PcmJitterBuffer(capacity_frames=4, prebuffer_frames=1)
    first_consumed = Event()
    consumed = []

    def consume(value):
        consumed.append(value)
        first_consumed.set()

    buffer.push(frame(1))
    thread = Thread(target=lambda: buffer.play(consume))
    thread.start()
    assert first_consumed.wait(timeout=1)
    time.sleep(0.2)
    buffer.push(frame(2))
    buffer.complete()
    thread.join(timeout=1)

    assert consumed == [frame(1), frame(2)]
    assert buffer.metrics().refill_deadline_misses >= 1
