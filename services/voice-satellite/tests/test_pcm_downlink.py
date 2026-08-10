import base64
import json
from threading import Event

import pytest

from kyrion_voice_satellite.pcm_downlink import (
    FRAME_BYTES,
    PcmDownlinkClient,
    PcmDownlinkError,
)


class StreamingResponse:
    def __init__(self, events):
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(json.dumps(event).encode() + b"\n" for event in self._events)


def event(event_type, **fields):
    return {"type": event_type, "sessionId": "session", "turnId": "turn", **fields}


def client(tmp_path, events, *, now=1_010):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    return PcmDownlinkClient(
        "http://core", "satellite", credential,
        epoch_millis=lambda: now,
        urlopen=lambda *_args, **_kwargs: StreamingResponse(events),
    )


def valid_events(frame_count=2):
    encoded = base64.b64encode(bytes(FRAME_BYTES)).decode()
    return [
        event("start", sampleRate=24_000, channels=1, frameMilliseconds=160),
        *[
            event(
                "audio", sequence=sequence, producedAtEpochMillis=1_000,
                audioBase64=encoded,
            )
            for sequence in range(frame_count)
        ],
        event("complete", framesSent=frame_count, pcmBytesSent=FRAME_BYTES * frame_count),
    ]


def test_receives_scoped_ordered_pcm_without_playback(tmp_path):
    frames = []

    result = client(tmp_path, valid_events()).receive(
        "session", "turn", 320, frames.append,
    )

    assert result.status == "completed"
    assert result.frames_received == 2
    assert result.pcm_bytes_received == FRAME_BYTES * 2
    assert result.first_frame_latency_millis == 10
    assert len(frames) == 2


def test_rejects_sequence_gap_before_consuming_bad_frame(tmp_path):
    events = valid_events()
    events[2]["sequence"] = 3
    frames = []

    with pytest.raises(PcmDownlinkError, match="sequence"):
        client(tmp_path, events).receive("session", "turn", 320, frames.append)

    assert len(frames) == 1


def test_rejects_cross_turn_audio(tmp_path):
    events = valid_events(1)
    events[1]["turnId"] = "old-turn"

    with pytest.raises(PcmDownlinkError, match="scope"):
        client(tmp_path, events).receive("session", "turn", 160, lambda _frame: None)


def test_cancellation_stops_before_audio_consumption(tmp_path):
    cancelled = Event()
    cancelled.set()
    frames = []

    result = client(tmp_path, valid_events(1)).receive(
        "session", "turn", 160, frames.append, cancelled=cancelled,
    )

    assert result.status == "cancelled"
    assert frames == []


def test_rejects_unbounded_or_misaligned_duration(tmp_path):
    with pytest.raises(PcmDownlinkError, match="duration"):
        client(tmp_path, []).receive("session", "turn", 161, lambda _frame: None)
