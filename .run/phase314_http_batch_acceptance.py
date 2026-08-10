from __future__ import annotations

import io
import json
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "services" / "ai" / "src"))

from kyrion_ai.config import Settings
from kyrion_ai.speech import SpeechService


def main() -> None:
    settings = Settings(
        "http://127.0.0.1:11434",
        "unused",
        ("unused",),
        1.0,
        tts_provider="http_batch",
        http_tts_url="http://127.0.0.1:8020",
    )
    service = SpeechService(settings)
    voices = service.voices()
    started = time.perf_counter()
    audio = service.synthesize("Velora ist als lokaler Batch-Fallback bereit.")
    elapsed = time.perf_counter() - started
    with wave.open(io.BytesIO(audio), "rb") as wav:
        result = {
            "defaultVoiceId": voices["defaultVoiceId"],
            "voiceCount": len(voices["voices"]),
            "elapsedSeconds": round(elapsed, 3),
            "bytes": len(audio),
            "channels": wav.getnchannels(),
            "sampleWidth": wav.getsampwidth(),
            "sampleRate": wav.getframerate(),
            "audioSeconds": round(wav.getnframes() / wav.getframerate(), 3),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
