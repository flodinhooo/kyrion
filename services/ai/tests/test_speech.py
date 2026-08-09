from pathlib import Path

import pytest

from kyrion_ai.config import Settings
from kyrion_ai.speech import InvalidAudioError, LocalSpeechService, SpeechUnavailableError


def settings() -> Settings:
    return Settings("http://127.0.0.1:11434", "model", ("model",), 1.0)


def test_transcription_rejects_non_wav_before_loading_runtime() -> None:
    with pytest.raises(InvalidAudioError):
        LocalSpeechService(settings()).transcribe(b"not audio", "de")


def test_synthesis_requires_explicit_local_provider() -> None:
    with pytest.raises(SpeechUnavailableError):
        LocalSpeechService(settings()).synthesize("Hallo")


def test_synthesis_rejects_missing_configured_files(tmp_path: Path) -> None:
    configured = Settings(
        "http://127.0.0.1:11434",
        "model",
        ("model",),
        1.0,
        piper_executable=str(tmp_path / "piper"),
        piper_model=str(tmp_path / "voice.onnx"),
    )
    with pytest.raises(SpeechUnavailableError):
        LocalSpeechService(configured).synthesize("Hallo")
