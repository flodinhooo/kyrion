import base64
import json
from unittest.mock import patch

import pytest

from kyrion_voice_satellite.core_client import CoreVoiceClient, CoreVoiceError


class StreamingResponse:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self._lines = [json.dumps(event).encode() + b"\n" for event in events]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b"".join(self._lines)

    def __iter__(self):
        return iter(self._lines)


def test_open_session_calibrates_satellite_clock_to_core(tmp_path):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    response = StreamingResponse([{
        "sessionId": "session",
        "conversationId": "conversation",
        "serverTimeEpochMillis": 1_250,
    }])

    with (
        patch("urllib.request.urlopen", return_value=response),
        patch("time.time_ns", return_value=1_100_000_000),
    ):
        session = CoreVoiceClient("http://core", "satellite", credential).open_session()

    assert session.clock_offset_millis == 150


def test_greeting_returns_valid_server_resolved_wav(tmp_path):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32
    response = StreamingResponse([{
        "responseText": "Hallo.",
        "audioBase64": base64.b64encode(wav).decode(),
    }])

    with patch("urllib.request.urlopen", return_value=response):
        audio = CoreVoiceClient("http://core", "satellite", credential).greeting(
            "session", "de",
        )

    assert audio == wav


def test_greeting_rejects_invalid_audio(tmp_path):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    response = StreamingResponse([{
        "responseText": "Hallo.",
        "audioBase64": base64.b64encode(b"not-a-wave").decode(),
    }])

    with (
        patch("urllib.request.urlopen", return_value=response),
        pytest.raises(CoreVoiceError, match="invalid greeting"),
    ):
        CoreVoiceClient("http://core", "satellite", credential).greeting("session", "de")


def test_turn_plays_audio_chunks_before_completion(tmp_path):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    first = b"first-wave"
    second = b"second-wave"
    response = StreamingResponse(
        [
            {"type": "transcript", "transcript": "Wer bist du?"},
            {"type": "audio.chunk", "audioBase64": base64.b64encode(first).decode()},
            {"type": "audio.chunk", "audioBase64": base64.b64encode(second).decode()},
            {
                "type": "completed",
                "responseText": "Eine vollständige Antwort.",
                "continueSession": True,
            },
        ],
    )
    played: list[bytes] = []

    with patch("urllib.request.urlopen", return_value=response):
        turn = CoreVoiceClient("http://core", "satellite", credential).turn(
            "session", b"RIFF-audio", "de", played.append, "turn-id",
        )

    assert played == [first, second]
    assert turn.transcript == "Wer bist du?"
    assert turn.response_text == "Eine vollständige Antwort."
    assert turn.continue_session is True
    assert turn.restart_session is False


def test_turn_acknowledges_required_playback_only_after_playing(tmp_path):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    audio = b"processing-wave"
    response = StreamingResponse(
        [
            {"type": "transcript", "transcript": "Schalte das Licht an."},
            {
                "type": "audio.chunk",
                "audioBase64": base64.b64encode(audio).decode(),
                "playbackAcknowledgementRequired": True,
            },
            {
                "type": "completed",
                "responseText": "Erledigt.",
                "continueSession": True,
            },
        ],
    )
    order: list[str] = []
    acknowledgement = StreamingResponse([{"status": "acknowledged"}])

    def urlopen(request, timeout=0):
        if request.full_url.endswith("/playback-completed"):
            order.append("acknowledged")
            return acknowledgement
        return response

    with patch("urllib.request.urlopen", side_effect=urlopen):
        CoreVoiceClient("http://core", "satellite", credential).turn(
            "session",
            b"RIFF-audio",
            "de",
            lambda _audio: order.append("played"),
            "turn-id",
        )

    assert order == ["played", "acknowledged"]


def test_pending_action_executes_only_after_processing_playback(tmp_path):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    processing = b"processing-wave"
    final = b"final-wave"
    response = StreamingResponse([
        {"type": "transcript", "transcript": "Schalte das Licht an."},
        {"type": "audio.chunk", "audioBase64": base64.b64encode(processing).decode()},
        {"type": "action.pending", "pendingAction": True},
    ])
    completion = StreamingResponse([{
        "responseText": "Erledigt.",
        "audioBase64": base64.b64encode(final).decode(),
        "continueSession": True,
    }])
    order: list[str] = []

    def urlopen(request, timeout=0):
        if request.full_url.endswith("/execute"):
            order.append("execute")
            return completion
        return response

    with patch("urllib.request.urlopen", side_effect=urlopen):
        turn = CoreVoiceClient("http://core", "satellite", credential).turn(
            "session",
            b"RIFF-audio",
            "de",
            lambda audio: order.append(
                "processing-played" if audio == processing else "result-played"
            ),
            "turn-id",
        )

    assert order == ["processing-played", "execute", "result-played"]
    assert turn.response_text == "Erledigt."


def test_turn_exposes_requested_session_restart(tmp_path):
    credential = tmp_path / "credential"
    credential.write_text("secret", encoding="utf-8")
    response = StreamingResponse([
        {"type": "transcript", "transcript": "Hey Willorra!"},
        {
            "type": "completed",
            "responseText": "Session restart",
            "continueSession": False,
            "restartSession": True,
        },
    ])

    with patch("urllib.request.urlopen", return_value=response):
        turn = CoreVoiceClient("http://core", "satellite", credential).turn(
            "session", b"RIFF-audio", "de", lambda _audio: None, "turn-id",
        )

    assert turn.restart_session is True
