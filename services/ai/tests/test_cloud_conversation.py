import asyncio
import io
import wave
from dataclasses import replace

import pytest

from kyrion_ai.cloud_conversation import (
    CloudConversationError,
    CloudConversationManager,
    _pcm_to_wav,
    _wav_pcm16_mono,
)
from kyrion_ai.config import Settings


class UnusedSpeech:
    pass


def settings(**changes) -> Settings:
    base = Settings("http://localhost:11434", "local", ("local",), 1.0)
    return replace(base, **changes)


def test_cloud_session_is_disabled_by_default() -> None:
    manager = CloudConversationManager(settings(), UnusedSpeech())
    with pytest.raises(CloudConversationError, match="disabled"):
        asyncio.run(manager.open("openrouter", "de"))


def test_openrouter_spike_rejects_paid_model() -> None:
    manager = CloudConversationManager(settings(
        cloud_conversation_enabled=True,
        openrouter_api_key="test-only",
        openrouter_model="provider/paid-model",
    ), UnusedSpeech())
    with pytest.raises(CloudConversationError, match="free models"):
        asyncio.run(manager.open("openrouter", "de"))


def test_gemini_audio_conversion_preserves_pcm() -> None:
    pcm = b"\x00\x01" * 320
    wav = _pcm_to_wav(pcm, 16_000)
    assert _wav_pcm16_mono(wav, 16_000) == pcm
    with wave.open(io.BytesIO(wav), "rb") as stream:
        assert stream.getframerate() == 16_000
