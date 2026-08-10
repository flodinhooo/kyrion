from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from threading import Event

import httpx

from kyrion_ai.streaming_tts import (
    ProviderPcmChunk,
    StreamingTtsCapabilities,
    StreamingTtsContractError,
    StreamingTtsRequest,
)

MAX_EVENT_CHARACTERS = 300_000


class XttsStreamingTtsAdapter:
    """Experimental XTTS-v2 adapter behind Kyrion's provider-neutral contract."""

    def __init__(self, base_url: str, client: httpx.Client) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._capabilities = self._discover()

    def _discover(self) -> StreamingTtsCapabilities:
        try:
            response = self._client.get(f"{self._base_url}/v1/streaming/capabilities")
            response.raise_for_status()
            value = response.json()
            return StreamingTtsCapabilities(
                provider_id=str(value["providerId"]),
                incremental_output=value["incrementalOutput"] is True,
                cancellation=value["cancellation"] is True,
                voice_cloning=value["voiceCloning"] is True,
                sample_format=value["sampleFormat"],
                sample_rate=int(value["sampleRate"]),
                channels=int(value["channels"]),
                minimum_text_granularity=value["minimumTextGranularity"],
                maximum_text_characters=int(value["maximumTextCharacters"]),
                maximum_chunk_milliseconds=int(value["maximumChunkMilliseconds"]),
                cancellation_deadline_milliseconds=int(value["cancellationDeadlineMilliseconds"]),
            )
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise StreamingTtsContractError("XTTS_CAPABILITIES_INVALID") from error

    @property
    def capabilities(self) -> StreamingTtsCapabilities:
        return self._capabilities

    def synthesize(
        self, request: StreamingTtsRequest, cancelled: Event
    ) -> Iterator[ProviderPcmChunk]:
        payload = {
            "turnId": str(request.turn_id),
            "text": request.text,
            "locale": request.locale,
            "voiceProfileId": request.voice_profile_id,
            "phraseIndex": request.phrase_index,
            "finalPhrase": request.final_phrase,
        }
        completed = False
        try:
            with self._client.stream(
                "POST", f"{self._base_url}/v1/synthesize/stream", json=payload
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if cancelled.is_set():
                        return
                    if not line:
                        continue
                    if completed or len(line) > MAX_EVENT_CHARACTERS:
                        raise StreamingTtsContractError("XTTS_EVENT_INVALID")
                    event = json.loads(line)
                    event_type = event.get("type")
                    if event_type == "audio":
                        yield ProviderPcmChunk(
                            sequence=int(event["sequence"]),
                            pcm=base64.b64decode(event["audioBase64"], validate=True),
                            produced_at_epoch_millis=int(event["producedAtEpochMillis"]),
                        )
                    elif event_type == "complete":
                        completed = True
                    elif event_type == "cancelled":
                        cancelled.set()
                        return
                    elif event_type == "error":
                        raise StreamingTtsContractError("XTTS_PROVIDER_ERROR")
                    else:
                        raise StreamingTtsContractError("XTTS_EVENT_INVALID")
        except StreamingTtsContractError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise StreamingTtsContractError("XTTS_STREAM_INVALID") from error
        if not completed and not cancelled.is_set():
            raise StreamingTtsContractError("XTTS_STREAM_DISCONNECTED")
