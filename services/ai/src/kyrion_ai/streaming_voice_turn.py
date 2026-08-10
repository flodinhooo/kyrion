from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from threading import Event
from typing import Literal
from uuid import UUID

from kyrion_ai.streaming_tts import (
    StreamingTtsRequest,
    TtsStreamAudio,
    ValidatedStreamingTts,
)
from kyrion_ai.tts_phrase_boundary import segment_tts_phrases


@dataclass(frozen=True, slots=True)
class VoiceTurnAudio:
    type: Literal["audio"]
    turn_id: UUID
    phrase_index: int
    sequence: int
    pcm: bytes
    produced_at_epoch_millis: int


@dataclass(frozen=True, slots=True)
class VoiceTurnTerminal:
    type: Literal["complete", "cancelled"]
    turn_id: UUID
    phrases: int
    chunks: int
    pcm_bytes: int


VoiceTurnEvent = VoiceTurnAudio | VoiceTurnTerminal


def stream_voice_turn(
    tokens: Iterable[str],
    tts: ValidatedStreamingTts,
    turn_id: UUID,
    locale: Literal["de", "en"],
    voice_profile_id: str,
    cancelled: Event,
) -> Iterator[VoiceTurnEvent]:
    """Compose text segmentation and TTS without provider or Core coupling."""

    phrases = 0
    chunks = 0
    pcm_bytes = 0
    for phrase in segment_tts_phrases(tokens, cancelled):
        request = StreamingTtsRequest(
            turn_id,
            phrase.text,
            locale,
            voice_profile_id,
            phrase.index,
            phrase.final,
        )
        for event in tts.stream(request, cancelled):
            if isinstance(event, TtsStreamAudio):
                yield VoiceTurnAudio(
                    "audio",
                    turn_id,
                    phrase.index,
                    event.sequence,
                    event.pcm,
                    event.produced_at_epoch_millis,
                )
                chunks += 1
                pcm_bytes += len(event.pcm)
        if cancelled.is_set():
            yield VoiceTurnTerminal(
                "cancelled", turn_id, phrases, chunks, pcm_bytes
            )
            return
        phrases += 1
    terminal_type = "cancelled" if cancelled.is_set() else "complete"
    yield VoiceTurnTerminal(terminal_type, turn_id, phrases, chunks, pcm_bytes)
