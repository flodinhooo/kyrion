from pathlib import Path

from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient
from kyrion_voice_satellite.playback import PipeWirePlayback

config = SatelliteConfig.load(Path("/home/flodinho/.config/kyrion/voice-satellite.json"))
client = CoreVoiceClient(config.core_url, config.satellite_id, config.credential_file)
session = client.open_session()
try:
    audio = client.greeting(session.id, config.locale)
    PipeWirePlayback(config.playback_target).play(audio)
    print(f"greeting_bytes={len(audio)}")
finally:
    client.close_session(session.id, "diagnostic")
