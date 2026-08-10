from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO, Protocol

from kyrion_voice_satellite.pcm_downlink import (
    CHANNELS,
    FRAME_BYTES,
    SAMPLE_RATE,
)


class PcmPipeWireError(RuntimeError):
    pass


class PipeWireProcess(Protocol):
    stdin: BinaryIO | None
    stderr: BinaryIO | None

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PcmPipeWireResult:
    status: str
    frames_written: int
    pcm_bytes_written: int


class PipeWirePcmSink:
    """One bounded raw-PCM pw-play process for one voice turn."""

    def __init__(
        self,
        target: str | None = None,
        *,
        latency_milliseconds: int = 320,
        process_factory: Callable[..., PipeWireProcess] = subprocess.Popen,
    ) -> None:
        if latency_milliseconds not in range(40, 1_001):
            raise ValueError("PipeWire latency must be between 40 and 1000 ms")
        command = [
            "pw-play",
            "--raw",
            "--rate",
            str(SAMPLE_RATE),
            "--channels",
            str(CHANNELS),
            "--format",
            "s16",
            "--latency",
            f"{latency_milliseconds}ms",
        ]
        if target is not None:
            command.extend(["--target", target])
        command.append("-")
        self._process = process_factory(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        if self._process.stdin is None:
            raise PcmPipeWireError("PipeWire stdin was unavailable")
        self._frames = 0
        self._bytes = 0
        self._closed = False

    def write(self, frame: bytes) -> None:
        if self._closed:
            raise PcmPipeWireError("PipeWire sink is closed")
        if len(frame) != FRAME_BYTES:
            raise PcmPipeWireError("PipeWire sink received an invalid PCM frame")
        if self._process.poll() is not None:
            raise PcmPipeWireError("PipeWire stopped before the turn completed")
        try:
            assert self._process.stdin is not None
            written = self._process.stdin.write(frame)
        except (BrokenPipeError, OSError) as error:
            raise PcmPipeWireError("PipeWire rejected PCM audio") from error
        if written != len(frame):
            raise PcmPipeWireError("PipeWire accepted only a partial PCM frame")
        self._frames += 1
        self._bytes += written

    def complete(self) -> PcmPipeWireResult:
        if self._closed:
            raise PcmPipeWireError("PipeWire sink is closed")
        self._closed = True
        assert self._process.stdin is not None
        self._process.stdin.close()
        try:
            return_code = self._process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            self._process.kill()
            self._process.wait(timeout=2)
            raise PcmPipeWireError("PipeWire did not finish the turn") from error
        if return_code != 0:
            raise PcmPipeWireError("PipeWire playback failed")
        return PcmPipeWireResult("completed", self._frames, self._bytes)

    def cancel(self) -> PcmPipeWireResult:
        if not self._closed:
            self._closed = True
            self._process.terminate()
            try:
                self._process.wait(timeout=0.05)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1)
        return PcmPipeWireResult("cancelled", self._frames, self._bytes)
