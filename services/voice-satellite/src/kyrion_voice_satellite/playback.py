from __future__ import annotations

import subprocess
import tempfile


class PipeWirePlayback:
    def __init__(self, target: str | None = None) -> None:
        self._target = target

    def play(self, wav: bytes) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            audio.write(wav)
            audio.flush()
            command = ["pw-play"]
            if self._target is not None:
                command.extend(["--target", self._target])
            command.append(audio.name)
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60,
            )
        if result.returncode != 0:
            raise RuntimeError("PipeWire playback failed")
