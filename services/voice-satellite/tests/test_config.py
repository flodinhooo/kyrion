import json
from pathlib import Path

import pytest

from kyrion_voice_satellite.config import SatelliteConfig


def test_config_accepts_only_bounded_local_audio_and_model_values(tmp_path: Path) -> None:
    path = tmp_path / "satellite.json"
    path.write_text(json.dumps({
        "model_path": "/var/lib/kyrion-voice/models/hey-velora.onnx",
        "capture_device": "hw:CARD=M20672,DEV=0",
        "threshold": 0.62,
        "cooldown_seconds": 2.5,
    }), encoding="utf-8")

    config = SatelliteConfig.load(path)

    assert config.threshold == 0.62
    assert config.capture_device == "hw:CARD=M20672,DEV=0"


def test_config_accepts_absolute_cached_greeting(tmp_path: Path) -> None:
    path = tmp_path / "satellite.json"
    path.write_text(json.dumps({
        "model_path": "/model.onnx",
        "capture_device": "hw:CARD=USB,DEV=0",
        "greeting_audio_file": "/home/user/.local/share/kyrion/greeting.wav",
        "playback_target": "bluez_output.00_02_3C_CE_31_40.1",
    }), encoding="utf-8")

    config = SatelliteConfig.load(path)

    assert config.greeting_audio_file == Path("/home/user/.local/share/kyrion/greeting.wav")
    assert config.playback_target == "bluez_output.00_02_3C_CE_31_40.1"


def test_config_accepts_bounded_pcm_uplink_mode(tmp_path: Path) -> None:
    path = tmp_path / "satellite.json"
    path.write_text(json.dumps({
        "model_path": "/model.onnx",
        "capture_device": "hw:CARD=USB,DEV=0",
        "core_url": "http://core:8080",
        "satellite_id": "satellite-id",
        "credential_file": "/run/kyrion/voice.token",
        "dialogue_mode": "pcm-uplink",
    }), encoding="utf-8")

    config = SatelliteConfig.load(path)

    assert config.dialogue_mode == "pcm-uplink"


@pytest.mark.parametrize("field,value", [
    ("model_path", "relative.onnx"),
    ("capture_device", "default"),
    ("threshold", 0),
    ("cooldown_seconds", 31),
    ("dialogue_mode", "websocket"),
])
def test_config_rejects_unbounded_values(tmp_path: Path, field: str, value: object) -> None:
    data = {"model_path": "/model.onnx", "capture_device": "hw:CARD=USB,DEV=0"}
    data[field] = value
    path = tmp_path / "satellite.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        SatelliteConfig.load(path)
