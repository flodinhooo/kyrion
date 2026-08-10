from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from threading import Event
from typing import Literal, Protocol
from uuid import UUID

PcmSampleFormat = Literal["pcm_s16le"]
TextGranularity = Literal["phrase", "sentence", "document"]


class StreamingTtsContractError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StreamingTtsCapabilities:
    provider_id: str
    incremental_output: bool
    cancellation: bool
    voice_cloning: bool
    sample_format: PcmSampleFormat
    sample_rate: int
    channels: int
    minimum_text_granularity: TextGranularity
    maximum_text_characters: int
    maximum_chunk_milliseconds: int
    cancellation_deadline_milliseconds: int = 250


@dataclass(frozen=True, slots=True)
class StreamingTtsRequest:
    turn_id: UUID
    text: str
    locale: Literal["de", "en"]
    voice_profile_id: str
    phrase_index: int
    final_phrase: bool


@dataclass(frozen=True, slots=True)
class ProviderPcmChunk:
    sequence: int
    pcm: bytes
    produced_at_epoch_millis: int


@dataclass(frozen=True, slots=True)
class TtsStreamStarted:
    type: Literal["start"]
    turn_id: UUID
    sample_format: PcmSampleFormat
    sample_rate: int
    channels: int
    minimum_text_granularity: TextGranularity


@dataclass(frozen=True, slots=True)
class TtsStreamAudio:
    type: Literal["audio"]
    turn_id: UUID
    sequence: int
    pcm: bytes
    produced_at_epoch_millis: int


@dataclass(frozen=True, slots=True)
class TtsStreamCompleted:
    type: Literal["complete"]
    turn_id: UUID
    chunks: int
    pcm_bytes: int


@dataclass(frozen=True, slots=True)
class TtsStreamCancelled:
    type: Literal["cancelled"]
    turn_id: UUID
    chunks: int
    pcm_bytes: int


TtsStreamEvent = TtsStreamStarted | TtsStreamAudio | TtsStreamCompleted | TtsStreamCancelled


class StreamingTtsProvider(Protocol):
    @property
    def capabilities(self) -> StreamingTtsCapabilities: ...

    def synthesize(
        self, request: StreamingTtsRequest, cancelled: Event
    ) -> Iterator[ProviderPcmChunk]: ...


class ValidatedStreamingTts:
    """Validates untrusted provider output before it can cross the AI boundary."""

    def __init__(self, provider: StreamingTtsProvider) -> None:
        self._provider = provider
        self._validate_capabilities(provider.capabilities)

    @property
    def capabilities(self) -> StreamingTtsCapabilities:
        return self._provider.capabilities

    def stream(
        self, request: StreamingTtsRequest, cancelled: Event
    ) -> Iterator[TtsStreamEvent]:
        capabilities = self.capabilities
        text = request.text.strip()
        if not text or len(text) > capabilities.maximum_text_characters:
            raise StreamingTtsContractError("TTS_TEXT_INVALID")
        if request.phrase_index < 0 or not request.voice_profile_id:
            raise StreamingTtsContractError("TTS_REQUEST_INVALID")

        yield TtsStreamStarted(
            "start",
            request.turn_id,
            capabilities.sample_format,
            capabilities.sample_rate,
            capabilities.channels,
            capabilities.minimum_text_granularity,
        )
        chunks = 0
        pcm_bytes = 0
        bytes_per_sample_frame = capabilities.channels * 2
        maximum_chunk_bytes = (
            capabilities.sample_rate
            * bytes_per_sample_frame
            * capabilities.maximum_chunk_milliseconds
            // 1_000
        )
        maximum_turn_bytes = capabilities.sample_rate * bytes_per_sample_frame * 120

        for expected_sequence, chunk in enumerate(
            self._provider.synthesize(request, cancelled)
        ):
            if cancelled.is_set():
                yield TtsStreamCancelled("cancelled", request.turn_id, chunks, pcm_bytes)
                return
            if chunk.sequence != expected_sequence:
                raise StreamingTtsContractError("TTS_SEQUENCE_INVALID")
            if (
                not chunk.pcm
                or len(chunk.pcm) % bytes_per_sample_frame != 0
                or len(chunk.pcm) > maximum_chunk_bytes
            ):
                raise StreamingTtsContractError("TTS_AUDIO_INVALID")
            if pcm_bytes + len(chunk.pcm) > maximum_turn_bytes:
                raise StreamingTtsContractError("TTS_LIMIT_EXCEEDED")
            yield TtsStreamAudio(
                "audio",
                request.turn_id,
                chunk.sequence,
                chunk.pcm,
                chunk.produced_at_epoch_millis,
            )
            chunks += 1
            pcm_bytes += len(chunk.pcm)

        terminal = TtsStreamCancelled if cancelled.is_set() else TtsStreamCompleted
        terminal_type = "cancelled" if cancelled.is_set() else "complete"
        yield terminal(terminal_type, request.turn_id, chunks, pcm_bytes)

    @staticmethod
    def _validate_capabilities(capabilities: StreamingTtsCapabilities) -> None:
        if not capabilities.provider_id or not capabilities.incremental_output:
            raise StreamingTtsContractError("TTS_CAPABILITIES_INVALID")
        if not capabilities.cancellation or capabilities.cancellation_deadline_milliseconds > 250:
            raise StreamingTtsContractError("TTS_CANCELLATION_UNSUPPORTED")
        if capabilities.sample_format != "pcm_s16le":
            raise StreamingTtsContractError("TTS_FORMAT_UNSUPPORTED")
        if capabilities.sample_rate not in {16_000, 22_050, 24_000, 48_000}:
            raise StreamingTtsContractError("TTS_SAMPLE_RATE_UNSUPPORTED")
        if capabilities.channels != 1:
            raise StreamingTtsContractError("TTS_CHANNELS_UNSUPPORTED")
        if capabilities.maximum_text_characters not in range(1, 4_001):
            raise StreamingTtsContractError("TTS_CAPABILITIES_INVALID")
        if capabilities.maximum_chunk_milliseconds not in range(20, 2_001):
            raise StreamingTtsContractError("TTS_CAPABILITIES_INVALID")
