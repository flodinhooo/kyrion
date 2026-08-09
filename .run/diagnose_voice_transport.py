import json
import wave
from pathlib import Path

from kyrion_voice_satellite.core_client import CoreVoiceClient

home = Path.home()
config = json.loads((home / ".config/kyrion/voice-satellite.json").read_text())
source = home / ".local/share/kyrion/voice-satellite/recordings/v5-positive-session.wav"
target = Path("/tmp/kyrion-voice-diagnostic.wav")
with wave.open(str(source), "rb") as reader:
    frames = reader.readframes(reader.getframerate() * 3)
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
    turn = client.turn(session.id, audio, "de")
    print(f"transport=ok response_audio_bytes={len(turn.audio)}")
finally:
    client.close_session(session.id, "diagnostic")
    target.unlink(missing_ok=True)
