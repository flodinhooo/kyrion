import json
from threading import Event

import pytest

from kyrion_voice_satellite.audio import FRAME_BYTES
from kyrion_voice_satellite.pcm_uplink import PcmUplinkClient, PcmUplinkError


class FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def read(self) -> bytes:
        return json.dumps({
            "status": "completed",
            "framesReceived": 2,
            "pcmBytesReceived": FRAME_BYTES * 2,
            "firstFrameLatencyMillis": 4,
            "maximumFrameLatencyMillis": 7,
        }).encode()


class FakeConnection:
    def __init__(self, response_status: int = 200) -> None:
        self.events: list[dict[str, object]] = []
        self.response_status = response_status
        self.closed = False
        self.headers: dict[str, str] = {}

    def request(self, _method, _path, body, headers, *, encode_chunked) -> None:
        assert encode_chunked is True
        self.headers = headers
        self.events = [json.loads(line) for line in body]

    def getresponse(self) -> FakeResponse:
        return FakeResponse(self.response_status)

    def close(self) -> None:
        self.closed = True


def make_client(tmp_path, connection: FakeConnection) -> PcmUplinkClient:
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    return PcmUplinkClient(
        "http://core:8080",
        "satellite-id",
        credential,
        connection_factory=lambda *_args, **_kwargs: connection,
        epoch_millis=lambda: 1234,
    )


def test_stream_sends_typed_ordered_pcm_events_and_authentication(tmp_path) -> None:
    connection = FakeConnection()
    result = make_client(tmp_path, connection).stream(
        "session-id", "turn-id", [bytes(FRAME_BYTES), bytes(FRAME_BYTES)],
    )

    assert [event["type"] for event in connection.events] == [
        "start", "audio", "audio", "complete",
    ]
    assert [event["sequence"] for event in connection.events[1:3]] == [0, 1]
    assert connection.events[1]["capturedAtEpochMillis"] == 1234
    assert connection.headers["Authorization"] == "Bearer secret"
    assert result.frames_received == 2
    assert connection.closed is True


def test_stream_emits_terminal_cancellation_without_later_audio(tmp_path) -> None:
    connection = FakeConnection()
    cancelled = Event()
    cancelled.set()

    make_client(tmp_path, connection).stream(
        "session-id", "turn-id", [bytes(FRAME_BYTES)], cancelled=cancelled,
    )

    assert [event["type"] for event in connection.events] == ["start", "cancel"]


def test_stream_rejects_invalid_capture_frame_before_sending_more_data(tmp_path) -> None:
    connection = FakeConnection()

    with pytest.raises(PcmUplinkError, match="invalid PCM frame"):
        make_client(tmp_path, connection).stream("session-id", "turn-id", [b"short"])

    assert connection.closed is True


def test_stream_surfaces_authentication_rejection(tmp_path) -> None:
    connection = FakeConnection(response_status=401)

    with pytest.raises(PcmUplinkError, match="HTTP 401"):
        make_client(tmp_path, connection).stream("session-id", "turn-id", [])


def test_reconnect_uses_a_fresh_sequence_start(tmp_path) -> None:
    first = FakeConnection()
    second = FakeConnection()
    connections = iter([first, second])
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    client = PcmUplinkClient(
        "http://core:8080", "satellite-id", credential,
        connection_factory=lambda *_args, **_kwargs: next(connections),
    )

    client.stream("session-id", "turn-one", [bytes(FRAME_BYTES)])
    client.stream("session-id", "turn-two", [bytes(FRAME_BYTES)])

    assert first.events[1]["sequence"] == 0
    assert second.events[1]["sequence"] == 0
