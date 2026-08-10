from pathlib import Path

from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.pcm_uplink_runner import PcmUplinkRunner

config = SatelliteConfig.load(Path("/home/flodinho/.config/kyrion/voice-satellite.json"))
PcmUplinkRunner(config).run_session()
