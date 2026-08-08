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


@pytest.mark.parametrize("field,value", [
    ("model_path", "relative.onnx"),
    ("capture_device", "default"),
    ("threshold", 0),
    ("cooldown_seconds", 31),
])
def test_config_rejects_unbounded_values(tmp_path: Path, field: str, value: object) -> None:
    data = {"model_path": "/model.onnx", "capture_device": "hw:CARD=USB,DEV=0"}
    data[field] = value
    path = tmp_path / "satellite.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        SatelliteConfig.load(path)
