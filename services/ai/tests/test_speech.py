import base64
import json
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

    assert (
        LocalSpeechService(
            configured, httpx.Client(transport=httpx.MockTransport(handler))
        ).voices()["defaultVoiceId"]
        == "velora"
    )


def xtts_capabilities() -> dict[str, object]:
    return {
        "providerId": "xtts-v2-experimental",
        "incrementalOutput": True,
        "cancellation": True,
        "voiceCloning": True,
        "sampleFormat": "pcm_s16le",
        "sampleRate": 24_000,
        "channels": 1,
        "minimumTextGranularity": "phrase",
        "maximumTextCharacters": 500,
        "maximumChunkMilliseconds": 2_000,
        "cancellationDeadlineMilliseconds": 250,
    }


def experimental_settings() -> Settings:
    return Settings(
        "http://127.0.0.1:11434",
        "model",
        ("model",),
        1.0,
        tts_provider="xtts",
        http_tts_url="http://chatterbox.local",
        xtts_experimental_enabled=True,
        xtts_tts_url="http://xtts.local",
    )


def stream_body(chunks: list[bytes]) -> bytes:
    events = [
        {
            "type": "audio",
            "sequence": index,
            "audioBase64": base64.b64encode(chunk).decode(),
            "producedAtEpochMillis": index,
        }
        for index, chunk in enumerate(chunks)
    ]
    events.append({"type": "complete"})
    return b"".join(json.dumps(event).encode() + b"\n" for event in events)


def test_xtts_requires_explicit_feature_flag() -> None:
    configured = Settings("http://127.0.0.1:11434", "model", ("model",), 1.0, tts_provider="xtts")

    with pytest.raises(SpeechUnavailableError, match="not enabled"):
        LocalSpeechService(configured).synthesize("Hallo")


def test_experimental_xtts_collects_valid_stream_as_wav() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/streaming/capabilities":
            return httpx.Response(200, json=xtts_capabilities())
        assert request.url == "http://xtts.local/v1/synthesize/stream"
        payload = json.loads(request.read())
        assert payload["locale"] == "en"
        return httpx.Response(200, content=stream_body([b"\0\0" * 9_600]))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    audio = LocalSpeechService(experimental_settings(), client).synthesize(
        "Hello Velora.", locale="en"
    )

    assert audio.startswith(b"RIFF")
    assert b"WAVE" in audio[:16]


def test_experimental_xtts_overlength_falls_back_to_chatterbox() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/v1/streaming/capabilities":
            return httpx.Response(200, json=xtts_capabilities())
        if request.url.host == "xtts.local":
            chunk = b"\0\0" * 48_000
            return httpx.Response(200, content=stream_body([chunk, chunk, chunk]))
        return httpx.Response(200, content=b"RIFFfallbackWAVE")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    audio = LocalSpeechService(experimental_settings(), client).synthesize("Ich bin Velora.")

    assert audio == b"RIFFfallbackWAVE"
    assert calls[-1] == "http://chatterbox.local/v1/synthesize"


def test_experimental_xtts_provider_error_falls_back_to_chatterbox() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/streaming/capabilities":
            return httpx.Response(200, json=xtts_capabilities())
        if request.url.host == "xtts.local":
            return httpx.Response(500)
        return httpx.Response(200, content=b"RIFFfallbackWAVE")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert (
        LocalSpeechService(experimental_settings(), client).synthesize("Hallo")
        == b"RIFFfallbackWAVE"
    )
