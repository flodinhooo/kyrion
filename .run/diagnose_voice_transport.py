import json
import time
import uuid
import wave
from pathlib import Path

from kyrion_voice_satellite.core_client import CoreVoiceClient

home = Path.home()
config = json.loads((home / ".config/kyrion/voice-satellite.json").read_text())
source = Path("/tmp/kyrion-diagnostic-source.wav")
target = Path("/tmp/kyrion-voice-diagnostic.wav")
with wave.open(str(source), "rb") as reader:
    frames = reader.readframes(reader.getnframes())
    channels = reader.getnchannels()
    width = reader.getsampwidth()
    rate = reader.getframerate()
with wave.open(str(target), "wb") as writer:
    writer.setnchannels(channels)
    writer.setsampwidth(width)
    writer.setframerate(rate)
    writer.writeframes(frames)
audio = target.read_bytes()
print(f"wav_bytes={len(audio)} header={audio[:12].hex()}")
client = CoreVoiceClient(
    config["core_url"], config["satellite_id"], Path(config["credential_file"])
)
session = client.open_session()
try:
    chunks = []
    started = time.perf_counter()
    first_audio_seconds = None

    def receive_audio(chunk: bytes) -> None:
        global first_audio_seconds
        if first_audio_seconds is None:
            first_audio_seconds = time.perf_counter() - started
        chunks.append(chunk)

    turn = client.turn(session.id, audio, "de", receive_audio, str(uuid.uuid4()))
    print(
        f"transport=ok audio_chunks={len(chunks)} "
        f"response_audio_bytes={sum(len(chunk) for chunk in chunks)} "
        f"first_audio_seconds={first_audio_seconds:.3f} "
        f"total_seconds={time.perf_counter() - started:.3f}"
    )
finally:
    try:
        client.close_session(session.id, "diagnostic")
    except Exception:
        pass
    target.unlink(missing_ok=True)
