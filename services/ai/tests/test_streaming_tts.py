from threading import Event
from uuid import uuid4

import pytest

from kyrion_ai.streaming_tts import (
    ProviderPcmChunk,
    StreamingTtsCapabilities,
    StreamingTtsContractError,
    StreamingTtsRequest,
    TtsStreamAudio,
    TtsStreamCancelled,
    TtsStreamCompleted,
    ValidatedStreamingTts,
)


class StubProvider:
    def __init__(self, chunks=None, capabilities=None):
        self._chunks = chunks or []
        self._capabilities = capabilities or StreamingTtsCapabilities(
            provider_id="stub",
            incremental_output=True,
            cancellation=True,
            voice_cloning=False,
            sample_format="pcm_s16le",
            sample_rate=24_000,
            channels=1,
            minimum_text_granularity="phrase",
            maximum_text_characters=500,
            maximum_chunk_milliseconds=160,
        )

    @property
    def capabilities(self):
        return self._capabilities

    def synthesize(self, _request, cancelled):
        for chunk in self._chunks:
            if cancelled.is_set():
                return
            yield chunk


def request():
    return StreamingTtsRequest(uuid4(), "Hallo Welt.", "de", "velora-f", 0, True)


def test_validates_and_scopes_incremental_pcm_events():
    provider = StubProvider([
        ProviderPcmChunk(0, bytes(7_680), 1_000),
        ProviderPcmChunk(1, bytes(7_680), 1_160),
    ])

    events = list(ValidatedStreamingTts(provider).stream(request(), Event()))

    assert [event.type for event in events] == ["start", "audio", "audio", "complete"]
    assert [event.sequence for event in events if isinstance(event, TtsStreamAudio)] == [0, 1]
    assert isinstance(events[-1], TtsStreamCompleted)
    assert events[-1].chunks == 2
    assert events[-1].pcm_bytes == 15_360


def test_rejects_provider_sequence_gap():
    provider = StubProvider([ProviderPcmChunk(1, bytes(7_680), 1_000)])

    with pytest.raises(StreamingTtsContractError, match="TTS_SEQUENCE_INVALID"):
        list(ValidatedStreamingTts(provider).stream(request(), Event()))


def test_rejects_oversized_provider_chunk():
    provider = StubProvider([ProviderPcmChunk(0, bytes(7_682), 1_000)])

    with pytest.raises(StreamingTtsContractError, match="TTS_AUDIO_INVALID"):
        list(ValidatedStreamingTts(provider).stream(request(), Event()))


def test_cancellation_emits_terminal_without_later_audio():
    cancelled = Event()
    provider = StubProvider([
        ProviderPcmChunk(0, bytes(7_680), 1_000),
        ProviderPcmChunk(1, bytes(7_680), 1_160),
    ])
    stream = ValidatedStreamingTts(provider).stream(request(), cancelled)

    start = next(stream)
    first_audio = next(stream)
    cancelled.set()
    terminal = next(stream)

    assert start.type == "start"
    assert isinstance(first_audio, TtsStreamAudio)
    assert isinstance(terminal, TtsStreamCancelled)
    assert list(stream) == []


def test_rejects_provider_without_bounded_cancellation():
    capabilities = StubProvider().capabilities
    unsupported = StreamingTtsCapabilities(
        **{
            field: getattr(capabilities, field)
            for field in capabilities.__dataclass_fields__
            if field != "cancellation_deadline_milliseconds"
        },
        cancellation_deadline_milliseconds=500,
    )

    with pytest.raises(StreamingTtsContractError, match="TTS_CANCELLATION_UNSUPPORTED"):
        ValidatedStreamingTts(StubProvider(capabilities=unsupported))


def test_rejects_document_larger_than_provider_contract():
    oversized = StreamingTtsRequest(uuid4(), "x" * 501, "de", "velora-f", 0, True)

    with pytest.raises(StreamingTtsContractError, match="TTS_TEXT_INVALID"):
        list(ValidatedStreamingTts(StubProvider()).stream(oversized, Event()))

