import io
import subprocess

import pytest

from kyrion_voice_satellite.pcm_downlink import FRAME_BYTES
from kyrion_voice_satellite.pcm_pipewire import PcmPipeWireError, PipeWirePcmSink


class FakeProcess:
    def __init__(self, return_code=0):
        self.stdin = io.BytesIO()
        self.stderr = io.BytesIO()
        self.return_code = return_code
        self.terminated = False
        self.killed = False

    def poll(self):
        return None

    def wait(self, timeout=None):
        return self.return_code

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class SlowTerminateProcess(FakeProcess):
    def wait(self, timeout=None):
        if self.terminated and not self.killed:
            raise subprocess.TimeoutExpired("pw-play", timeout)
        return self.return_code


def factory(captured, process):
    def create(command, **options):
        captured["command"] = command
        captured["options"] = options
        return process

    return create


def test_streams_raw_pcm_to_explicit_pipewire_target():
    captured = {}
    process = FakeProcess()
    sink = PipeWirePcmSink(
        "pebble", process_factory=factory(captured, process), latency_milliseconds=320
    )
    payload = bytes(FRAME_BYTES)

    sink.write(payload)
    assert process.stdin.getvalue() == payload
    result = sink.complete()

    assert captured["command"] == [
        "pw-play", "--raw", "--rate", "24000", "--channels", "1",
        "--format", "s16", "--latency", "320ms", "--target", "pebble", "-",
    ]
    assert result.status == "completed"
    assert result.frames_written == 1


def test_cancellation_terminates_process_and_rejects_later_audio():
    process = FakeProcess()
    sink = PipeWirePcmSink(process_factory=factory({}, process))

    result = sink.cancel()

    assert result.status == "cancelled"
    assert process.terminated is True
    with pytest.raises(PcmPipeWireError, match="closed"):
        sink.write(bytes(FRAME_BYTES))


def test_cancellation_kills_a_pipewire_process_that_ignores_terminate():
    process = SlowTerminateProcess()
    sink = PipeWirePcmSink(process_factory=factory({}, process))

    sink.cancel()

    assert process.terminated is True
    assert process.killed is True


def test_rejects_invalid_frame_before_writing():
    process = FakeProcess()
    sink = PipeWirePcmSink(process_factory=factory({}, process))

    with pytest.raises(PcmPipeWireError, match="invalid PCM frame"):
        sink.write(b"short")

    assert process.stdin.getvalue() == b""


def test_surfaces_nonzero_pipewire_exit():
    sink = PipeWirePcmSink(process_factory=factory({}, FakeProcess(return_code=1)))

    with pytest.raises(PcmPipeWireError, match="playback failed"):
        sink.complete()
