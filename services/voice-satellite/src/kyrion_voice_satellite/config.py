from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SatelliteConfig:
    model_path: Path
    capture_device: str
    threshold: float = 0.5
    cooldown_seconds: float = 2.0

    @classmethod
    def load(cls, path: Path) -> SatelliteConfig:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Satellite configuration must be an object")
        model_path = value.get("model_path")
        capture_device = value.get("capture_device")
        threshold = value.get("threshold", 0.5)
        cooldown = value.get("cooldown_seconds", 2.0)
        if not isinstance(model_path, str) or not model_path.startswith("/"):
            raise ValueError("Model path must be absolute")
        if not isinstance(capture_device, str) or not capture_device.startswith("hw:"):
            raise ValueError("Capture device must be a bounded ALSA hardware selector")
        if not isinstance(threshold, (int, float)) or not 0.0 < float(threshold) <= 1.0:
            raise ValueError("Threshold must be between zero and one")
        if not isinstance(cooldown, (int, float)) or not 0.5 <= float(cooldown) <= 30.0:
            raise ValueError("Cooldown must be between 0.5 and 30 seconds")
        return cls(Path(model_path), capture_device, float(threshold), float(cooldown))
