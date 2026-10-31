from types import SimpleNamespace
from unittest.mock import Mock, patch

from kyrion_voice_satellite.core_client import VoiceTurn
from kyrion_voice_satellite.dialogue import DialogueRunner, DialogueState
from kyrion_voice_satellite.utterance import Utterance


def runner_with_turn(turn):
    runner = DialogueRunner.__new__(DialogueRunner)
    runner._config = SimpleNamespace(
        locale="de",
        capture_device="synthetic",
        speech_start_timeout_seconds=6,
        speech_end_silence_seconds=2,
        utterance_max_seconds=20,
    )
    runner._client = Mock()
    runner._client.open_session.return_value = SimpleNamespace(id="session")
    runner._client.greeting.return_value = b"greeting"
    runner._client.turn.return_value = turn
    runner._vad = Mock()
    runner._playback = Mock()
    runner._legacy_greeting_audio = None
    return runner


def test_no_speech_returns_to_idle_without_reclosing_or_retrying(caplog):
    runner = runner_with_turn(VoiceTurn("", "", False, False, outcome="no_speech"))
    with (
        patch("kyrion_voice_satellite.dialogue.AlsaCapture"),
        patch(
            "kyrion_voice_satellite.dialogue.capture_utterance",
            return_value=Utterance(b"pcm", 1, "silence"),
        ),
    ):
        assert runner._run_session_once() is False
    assert runner.state is DialogueState.IDLE
    runner._client.turn.assert_called_once()
    runner._client.close_session.assert_not_called()
    runner._playback.play.assert_called_once_with(b"greeting")


def test_normal_answer_keeps_followup_then_closes_on_inactivity():
    runner = runner_with_turn(VoiceTurn("question", "answer", True, False))
    with (
        patch("kyrion_voice_satellite.dialogue.AlsaCapture"),
        patch(
            "kyrion_voice_satellite.dialogue.capture_utterance",
            side_effect=[Utterance(b"pcm", 5, "silence"), None],
        ),
    ):
        assert runner._run_session_once() is False
    runner._client.close_session.assert_called_once_with("session", "inactivity")
    assert runner.state is DialogueState.IDLE
