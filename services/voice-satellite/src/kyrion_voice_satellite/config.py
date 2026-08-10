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
    speech_start_timeout_seconds: float = 6.0
    speech_end_silence_seconds: float = 0.8
    utterance_max_seconds: float = 20.0
    core_url: str | None = None
    satellite_id: str | None = None
    credential_file: Path | None = None
    locale: str = "de"
    greeting_audio_file: Path | None = None
    playback_target: str | None = None
    dialogue_mode: str = "batch"

    @classmethod
    def load(cls, path: Path) -> SatelliteConfig:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Satellite configuration must be an object")
        model_path = value.get("model_path")
        capture_device = value.get("capture_device")
        threshold = value.get("threshold", 0.5)
        cooldown = value.get("cooldown_seconds", 2.0)
        speech_start_timeout = value.get("speech_start_timeout_seconds", 6.0)
        speech_end_silence = value.get("speech_end_silence_seconds", 0.8)
        utterance_max = value.get("utterance_max_seconds", 20.0)
        core_url = value.get("core_url")
        satellite_id = value.get("satellite_id")
        credential_file = value.get("credential_file")
        locale = value.get("locale", "de")
        greeting_audio_file = value.get("greeting_audio_file")
        playback_target = value.get("playback_target")
        dialogue_mode = value.get("dialogue_mode", "batch")
        if not isinstance(model_path, str) or not model_path.startswith("/"):
            raise ValueError("Model path must be absolute")
        if not isinstance(capture_device, str) or not capture_device.startswith("hw:"):
            raise ValueError("Capture device must be a bounded ALSA hardware selector")
        if not isinstance(threshold, (int, float)) or not 0.0 < float(threshold) <= 1.0:
            raise ValueError("Threshold must be between zero and one")
        if not isinstance(cooldown, (int, float)) or not 0.5 <= float(cooldown) <= 30.0:
            raise ValueError("Cooldown must be between 0.5 and 30 seconds")
        if (
            not isinstance(speech_start_timeout, (int, float))
            or not 1.0 <= float(speech_start_timeout) <= 30.0
        ):
            raise ValueError("Speech start timeout must be between 1 and 30 seconds")
        if (
            not isinstance(speech_end_silence, (int, float))
            or not 0.3 <= float(speech_end_silence) <= 3.0
        ):
            raise ValueError("Speech end silence must be between 0.3 and 3 seconds")
        if not isinstance(utterance_max, (int, float)) or not 2.0 <= float(utterance_max) <= 60.0:
            raise ValueError("Utterance maximum must be between 2 and 60 seconds")
        dialogue_values = (core_url, satellite_id, credential_file)
        if any(item is not None for item in dialogue_values) and not all(
            isinstance(item, str) and item for item in dialogue_values
        ):
            raise ValueError("Dialogue configuration must be complete")
        if core_url is not None and not core_url.startswith(("http://", "https://")):
            raise ValueError("Core URL must use HTTP or HTTPS")
        if credential_file is not None and not credential_file.startswith("/"):
            raise ValueError("Credential file path must be absolute")
        if locale not in {"de", "en"}:
            raise ValueError("Locale must be de or en")
        if greeting_audio_file is not None and (
            not isinstance(greeting_audio_file, str) or not greeting_audio_file.startswith("/")
        ):
            raise ValueError("Greeting audio file path must be absolute")
        if playback_target is not None and (
            not isinstance(playback_target, str)
            or not playback_target.startswith("bluez_output.")
            or len(playback_target) > 160
        ):
            raise ValueError("Playback target must be a bounded Bluetooth sink name")
        if dialogue_mode not in {"batch", "pcm-uplink"}:
            raise ValueError("Dialogue mode must be batch or pcm-uplink")
        return cls(
            Path(model_path), capture_device, float(threshold), float(cooldown),
            float(speech_start_timeout), float(speech_end_silence), float(utterance_max),
            core_url, satellite_id, Path(credential_file) if credential_file else None, locale,
            Path(greeting_audio_file) if greeting_audio_file else None,
            playback_target,
            dialogue_mode,
        )

    @property
    def dialogue_enabled(self) -> bool:
        return self.core_url is not None
