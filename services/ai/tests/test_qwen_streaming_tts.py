import base64
import json
from threading import Event
from uuid import uuid4

import httpx
import pytest

from kyrion_ai.providers.qwen_streaming_tts import QwenStreamingTtsAdapter
from kyrion_ai.streaming_tts import (
    StreamingTtsContractError,
    StreamingTtsRequest,
    ValidatedStreamingTts,
)

CAPABILITIES = {
    "providerId": "qwen3-tts-1.7b",
    "incrementalOutput": True,
    "cancellation": True,
    "voiceCloning": True,
    "sampleFormat": "pcm_s16le",
    "sampleRate": 24_000,
    "channels": 1,
    "minimumTextGranularity": "phrase",
    "maximumTextCharacters": 500,
    "maximumChunkMilliseconds": 1_600,
    "cancellationDeadlineMilliseconds": 250,
}


def request():
    return StreamingTtsRequest(uuid4(), "Guten Abend.", "de", "velora-f", 2, False)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_discovers_capabilities_and_maps_qwen_pcm_stream():
    captured = {}
    pcm = bytes(7_680)

    def handler(http_request):
        if http_request.method == "GET":
            return httpx.Response(200, json=CAPABILITIES)
        captured["payload"] = json.loads(http_request.read())
        body = b"\n".join([
            json.dumps({
                "type": "audio",
                "sequence": 0,
                "audioBase64": base64.b64encode(pcm).decode(),
                "producedAtEpochMillis": 1_000,
            }).encode(),
            b'{"type":"complete"}',
        ])
        return httpx.Response(200, content=body)

    adapter = QwenStreamingTtsAdapter.discover("http://qwen", client(handler))
    events = list(ValidatedStreamingTts(adapter).stream(request(), Event()))

    assert adapter.capabilities.voice_cloning is True
    assert [event.type for event in events] == ["start", "audio", "complete"]
    assert captured["payload"]["voiceProfileId"] == "velora-f"
    assert captured["payload"]["phraseIndex"] == 2


def test_rejects_runtime_without_bounded_cancellation_capability():
    unsupported = {**CAPABILITIES, "cancellationDeadlineMilliseconds": 500}
    adapter = QwenStreamingTtsAdapter.discover(
        "http://qwen", client(lambda _request: httpx.Response(200, json=unsupported))
    )

    with pytest.raises(StreamingTtsContractError, match="TTS_CANCELLATION_UNSUPPORTED"):
        ValidatedStreamingTts(adapter)


def test_rejects_stream_disconnect_without_terminal_event():
    def handler(http_request):
        if http_request.method == "GET":
            return httpx.Response(200, json=CAPABILITIES)
        return httpx.Response(200, content=b"")

    adapter = QwenStreamingTtsAdapter.discover("http://qwen", client(handler))

    with pytest.raises(StreamingTtsContractError, match="QWEN_TTS_STREAM_DISCONNECTED"):
        list(adapter.synthesize(request(), Event()))


def test_cancellation_closes_stream_without_forwarding_later_audio():
    pcm = base64.b64encode(bytes(7_680)).decode()
    cancelled_turns = []

    def handler(http_request):
        if http_request.method == "GET":
            return httpx.Response(200, json=CAPABILITIES)
        if http_request.url.path.endswith("/cancel"):
            cancelled_turns.append(http_request.url.path)
            return httpx.Response(204)
        body = "\n".join([
            json.dumps({
                "type": "audio", "sequence": 0, "audioBase64": pcm,
                "producedAtEpochMillis": 1_000,
            }),
            json.dumps({
                "type": "audio", "sequence": 1, "audioBase64": pcm,
                "producedAtEpochMillis": 1_160,
            }),
            '{"type":"complete"}',
        ])
        return httpx.Response(200, content=body)

    adapter = QwenStreamingTtsAdapter.discover("http://qwen", client(handler))
    cancelled = Event()
    first_request = request()
    chunks = adapter.synthesize(first_request, cancelled)

    first = next(chunks)
    cancelled.set()

    assert first.sequence == 0
    assert list(chunks) == []
    assert cancelled_turns == [f"/v1/synthesize/{first_request.turn_id}/cancel"]


def test_rejects_audio_after_terminal_event():
    pcm = base64.b64encode(bytes(7_680)).decode()

    def handler(http_request):
        if http_request.method == "GET":
            return httpx.Response(200, json=CAPABILITIES)
        body = "\n".join([
            '{"type":"complete"}',
            json.dumps({
                "type": "audio", "sequence": 0, "audioBase64": pcm,
                "producedAtEpochMillis": 1_000,
            }),
        ])
        return httpx.Response(200, content=body)

    adapter = QwenStreamingTtsAdapter.discover("http://qwen", client(handler))

    with pytest.raises(StreamingTtsContractError, match="QWEN_TTS_EVENT_AFTER_TERMINAL"):
        list(adapter.synthesize(request(), Event()))
