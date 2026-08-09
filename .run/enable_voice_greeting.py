import json
from pathlib import Path

config_file = Path.home() / ".config/kyrion/voice-satellite.json"
config = json.loads(config_file.read_text(encoding="utf-8"))
config["greeting_audio_file"] = str(
    Path.home() / ".local/share/kyrion/voice-satellite/audio/velora-greeting.wav"
)
config["playback_target"] = "bluez_output.00_02_3C_CE_31_40.1"
config_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
