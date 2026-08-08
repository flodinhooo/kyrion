from __future__ import annotations

import subprocess
from collections.abc import Iterator

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 1_280
FRAME_BYTES = FRAME_SAMPLES * 2


class AlsaCapture:
    def __init__(self, device: str) -> None:
        self.device = device

    def frames(self) -> Iterator[bytes]:
        process = subprocess.Popen(
            [
                "arecord", "-q", "-D", self.device, "-t", "raw", "-f", "S16_LE",
                "-r", str(SAMPLE_RATE), "-c", "1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.stdout is None:
            process.kill()
            raise RuntimeError("Capture process has no audio stream")
        try:
            while True:
                frame = process.stdout.read(FRAME_BYTES)
                if len(frame) == FRAME_BYTES:
                    yield frame
                    continue
                if process.poll() is not None:
                    detail = process.stderr.read(200).decode("utf-8", errors="replace")
                    raise RuntimeError(f"Audio capture stopped: {detail.strip()}")
                raise RuntimeError("Audio capture returned a partial frame")
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
