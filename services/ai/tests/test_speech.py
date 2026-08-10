from pathlib import Path

import httpx
import pytest

from kyrion_ai.config import Settings
from kyrion_ai.speech import InvalidAudioError, LocalSpeechService, SpeechUnavailableError


def settings() -> Settings:
    return Settings("http://127.0.0.1:11434", "model", ("model",), 1.0)


def test_transcription_rejects_non_wav_before_loading_runtime() -> None:
    with pytest.raises(InvalidAudioError):
        LocalSpeechService(settings()).transcribe(b"not audio", "de")


def test_synthesis_reports_unavailable_http_batch_runtime() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(SpeechUnavailableError):
        LocalSpeechService(settings(), client).synthesize("Hallo")


def test_synthesis_rejects_missing_configured_files(tmp_path: Path) -> None:
    configured = Settings(
        "http://127.0.0.1:11434",
        "model",
        ("model",),
        1.0,
        tts_provider="piper",
        piper_executable=str(tmp_path / "piper"),
        piper_model=str(tmp_path / "voice.onnx"),
    )
    with pytest.raises(SpeechUnavailableError):
        LocalSpeechService(configured).synthesize("Hallo")


def test_http_batch_synthesis_uses_selected_voice_and_returns_wav() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://tts.local/v1/synthesize"
        assert request.read() == b'{"text":"Hallo & willkommen","voiceId":"sanft"}'
        return httpx.Response(200, content=b"RIFF0000WAVE")

    configured = Settings(
        "http://127.0.0.1:11434",
        "model",
        ("model",),
        1.0,
        http_tts_url="http://tts.local",
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    audio = LocalSpeechService(configured, client).synthesize("Hallo & willkommen", "sanft")

    assert audio == b"RIFF0000WAVE"


def test_explicit_legacy_qwen_provider_keeps_its_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://qwen.local/v1/voices"
        return httpx.Response(200, json={"defaultVoiceId": "velora", "voices": []})

    configured = Settings(
        "http://127.0.0.1:11434",
        "model",
        ("model",),
        1.0,
        tts_provider="qwen",
        qwen_tts_url="http://qwen.local",
    )

    assert LocalSpeechService(
        configured, httpx.Client(transport=httpx.MockTransport(handler))
    ).voices()["defaultVoiceId"] == "velora"
