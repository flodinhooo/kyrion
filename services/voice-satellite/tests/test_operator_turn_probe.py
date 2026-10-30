import importlib.util
import io
import socket
import urllib.error
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from kyrion_voice_satellite.core_client import CoreVoiceError

spec = importlib.util.spec_from_file_location(
    "operator_turn_probe", Path(__file__).parents[3] / "infrastructure/dev/Probe-VoiceTurn.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0" * 480)
    return output.getvalue()


def configured(monkeypatch):
    monkeypatch.setattr(
        module.SatelliteConfig,
        "load",
        lambda _: SimpleNamespace(
            core_url="http://core.test:8080",
            satellite_id="probe",
            credential_file=Path("/unused-credential"),
            locale="de",
        ),
    )
    client = Mock()
    client.open_session.return_value = SimpleNamespace(id="only-new-session")
    monkeypatch.setattr(module, "ReadOnlyActionClient", Mock(return_value=client))
    return client


def test_no_action_execution_or_playback_acknowledgement_is_permitted():
    client = object.__new__(module.ReadOnlyActionClient)
    for suffix in ("execute", "playback-completed"):
        with pytest.raises(CoreVoiceError, match="OPERATOR_PROBE_ACTION_FORBIDDEN"):
            client._request("POST", f"/turn/{suffix}", b"", "application/json")


def test_completed_stop_accepts_only_expected_already_closed_session(monkeypatch):
    client = configured(monkeypatch)

    def turn(_session, _audio, _locale, callback, _turn_id):
        callback(wav_bytes())
        return SimpleNamespace(transcript="Stopp.", response_text="reply", continue_session=False)

    client.turn.side_effect = turn
    error = CoreVoiceError("private error")
    error.__cause__ = urllib.error.HTTPError("http://core.test", 404, "closed", {}, None)
    client.close_session.side_effect = error
    original = socket.getaddrinfo
    result = module.probe(wav_bytes())
    assert result["turnCompleted"] and result["stopTranscribed"]
    assert result["responseAudioValid"] and result["sessionClosedByTurn"]
    assert result["sampleRates"] == [24000]
    assert not result["playbackPerformed"] and not result["microphoneOpened"]
    assert socket.getaddrinfo is original
    client.close_session.assert_called_once_with("only-new-session", "explicit")
    assert "private" not in str(result)


def test_auth_failure_is_not_mistaken_for_successful_session_cleanup(monkeypatch):
    client = configured(monkeypatch)
    client.turn.return_value = SimpleNamespace(
        transcript="Stopp.", response_text="reply", continue_session=False
    )
    error = CoreVoiceError("private token")
    error.__cause__ = urllib.error.HTTPError("http://core.test", 401, "denied", {}, None)
    client.close_session.side_effect = error
    result = module.probe(wav_bytes())
    assert not result["sessionClosed"]
    assert result["closeCode"] == "CoreVoiceError"
    assert "private" not in str(result)
