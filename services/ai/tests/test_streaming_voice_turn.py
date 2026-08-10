from collections.abc import Iterator
from threading import Event
from uuid import uuid4

from kyrion_ai.streaming_tts import (
    ProviderPcmChunk,
    StreamingTtsCapabilities,
    StreamingTtsRequest,
    ValidatedStreamingTts,
)
from kyrion_ai.streaming_voice_turn import stream_voice_turn


class SyntheticProvider:
    capabilities = StreamingTtsCapabilities(
        "synthetic", True, True, False, "pcm_s16le", 24_000, 1, "phrase", 500, 160
    )

    def __init__(self, cancel_on_phrase: int | None = None) -> None:
        self.requests: list[StreamingTtsRequest] = []
        self.cancel_on_phrase = cancel_on_phrase

    def synthesize(
        self, request: StreamingTtsRequest, cancelled: Event
    ) -> Iterator[ProviderPcmChunk]:
        self.requests.append(request)
        yield ProviderPcmChunk(0, bytes(7_680), 1_000 + request.phrase_index)
        if request.phrase_index == self.cancel_on_phrase:
            cancelled.set()
            return
        yield ProviderPcmChunk(1, bytes(7_680), 1_100 + request.phrase_index)


def test_composes_ordered_phrases_and_audio() -> None:
    provider = SyntheticProvider()
    events = list(
        stream_voice_turn(
            ["Guten Morgen. ", "Die desk lamp ist an."],
            ValidatedStreamingTts(provider),
            uuid4(),
            "de",
            "velora-f",
            Event(),
        )
    )

    audio = [event for event in events if event.type == "audio"]
    assert [(event.phrase_index, event.sequence) for event in audio] == [
        (0, 0), (0, 1), (1, 0), (1, 1)
    ]
    assert [request.text for request in provider.requests] == [
        "Guten Morgen.", "Die desk lamp ist an."
    ]
    assert events[-1].type == "complete"
    assert events[-1].phrases == 2
    assert events[-1].chunks == 4


def test_shared_cancellation_stops_later_phrases_once() -> None:
    provider = SyntheticProvider(cancel_on_phrase=0)
    cancelled = Event()
    events = list(
        stream_voice_turn(
            ["Die erste Antwort ist fertig. Die zweite darf nicht starten."],
            ValidatedStreamingTts(provider),
            uuid4(),
            "de",
            "velora-f",
            cancelled,
        )
    )

    assert len(provider.requests) == 1
    assert [event.type for event in events] == ["audio", "cancelled"]
    assert events[-1].chunks == 1
