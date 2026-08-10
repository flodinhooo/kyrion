from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from threading import Event, Lock, Thread

import httpx

from kyrion_ai.streaming_tts import (
    ProviderPcmChunk,
    StreamingTtsCapabilities,
    StreamingTtsContractError,
    StreamingTtsRequest,
)

MAX_EVENT_CHARACTERS = 300_000


class QwenStreamingTtsAdapter:
    """Adapter for a capability-reporting Qwen runtime; not a selected provider."""

    def __init__(
        self,
        base_url: str,
        http_client: httpx.Client,
        capabilities: StreamingTtsCapabilities,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http_client = http_client
        self._capabilities = capabilities

    @classmethod
    def discover(cls, base_url: str, http_client: httpx.Client) -> QwenStreamingTtsAdapter:
        try:
            response = http_client.get(f"{base_url.rstrip('/')}/v1/streaming/capabilities")
            response.raise_for_status()
            value = response.json()
            capabilities = StreamingTtsCapabilities(
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
                cancellation_deadline_milliseconds=int(
                    value["cancellationDeadlineMilliseconds"]
                ),
            )
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise StreamingTtsContractError("QWEN_TTS_CAPABILITIES_INVALID") from error
        return cls(base_url, http_client, capabilities)

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
        stream_finished = Event()
        cancel_sent = Event()
        cancel_lock = Lock()

        def signal_provider_cancellation() -> None:
            with cancel_lock:
                if cancel_sent.is_set():
                    return
                cancel_sent.set()
                try:
                    response = self._http_client.post(
                        f"{self._base_url}/v1/synthesize/{request.turn_id}/cancel"
                    )
                    if response.status_code != 404:
                        response.raise_for_status()
                except httpx.HTTPError:
                    # Closing the streaming response below remains the fallback.
                    pass

        def watch_cancellation() -> None:
            while not stream_finished.wait(0.01):
                if cancelled.is_set():
                    signal_provider_cancellation()
                    return

        watcher = Thread(target=watch_cancellation, daemon=True)
        watcher.start()
        try:
            with self._http_client.stream(
                "POST", f"{self._base_url}/v1/synthesize/stream", json=payload
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if cancelled.is_set():
                        signal_provider_cancellation()
                        return
                    if not line:
                        continue
                    if completed:
                        raise StreamingTtsContractError("QWEN_TTS_EVENT_AFTER_TERMINAL")
                    if len(line) > MAX_EVENT_CHARACTERS:
                        raise StreamingTtsContractError("QWEN_TTS_EVENT_TOO_LARGE")
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
                        raise StreamingTtsContractError("QWEN_TTS_PROVIDER_ERROR")
                    else:
                        raise StreamingTtsContractError("QWEN_TTS_EVENT_INVALID")
        except StreamingTtsContractError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise StreamingTtsContractError("QWEN_TTS_STREAM_INVALID") from error
        finally:
            stream_finished.set()
            watcher.join(timeout=0.3)
        if not completed and not cancelled.is_set():
            raise StreamingTtsContractError("QWEN_TTS_STREAM_DISCONNECTED")
