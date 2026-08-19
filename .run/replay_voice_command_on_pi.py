from pathlib import Path
import uuid

from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient


config = SatelliteConfig.load(Path("/home/flodinho/.config/kyrion/voice-satellite.json"))
assert config.core_url and config.satellite_id and config.credential_file
client = CoreVoiceClient(config.core_url, config.satellite_id, config.credential_file)
session = client.open_session()
chunks: list[int] = []
turn = client.turn(
    session.id,
    Path("/tmp/voice-command-replay.wav").read_bytes(),
    "de",
    lambda audio: chunks.append(len(audio)),
    str(uuid.uuid4()),
)
print({
    "transcript": turn.transcript,
    "response": turn.response_text,
    "continue": turn.continue_session,
    "audio_chunks": chunks,
})
client.close_session(session.id, "explicit")
