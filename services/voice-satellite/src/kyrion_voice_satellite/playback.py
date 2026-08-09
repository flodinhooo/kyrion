from __future__ import annotations

import subprocess
import tempfile


class PipeWirePlayback:
    def play(self, wav: bytes) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            audio.write(wav)
            audio.flush()
            result = subprocess.run(
                ["pw-play", audio.name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60,
            )
        if result.returncode != 0:
            raise RuntimeError("PipeWire playback failed")
