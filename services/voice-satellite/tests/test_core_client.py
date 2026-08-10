import base64
import json
from unittest.mock import patch

from kyrion_voice_satellite.core_client import CoreVoiceClient


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
