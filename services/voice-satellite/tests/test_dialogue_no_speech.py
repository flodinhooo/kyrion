from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from kyrion_voice_satellite.core_client import CoreVoiceError, VoiceTurn
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


def test_failed_close_returns_to_idle_without_replaying_and_next_session_can_run():
    runner = runner_with_turn(VoiceTurn("question", "answer", True, False))
    runner._client.close_session.side_effect = CoreVoiceError("synthetic disconnect")
    with (
        patch("kyrion_voice_satellite.dialogue.AlsaCapture"),
        patch("kyrion_voice_satellite.dialogue.capture_utterance", return_value=None),
        pytest.raises(CoreVoiceError, match="synthetic disconnect"),
    ):
        runner._run_session_once()
    assert runner.state is DialogueState.IDLE
    runner._client.close_session.assert_called_once_with("session", "inactivity")
    runner._client.close_session.side_effect = None
    with (
        patch("kyrion_voice_satellite.dialogue.AlsaCapture"),
        patch("kyrion_voice_satellite.dialogue.capture_utterance", return_value=None),
    ):
        assert runner._run_session_once() is False
    assert runner.state is DialogueState.IDLE
    assert runner._client.open_session.call_count == 2
    runner._client.turn.assert_not_called()


def test_first_chunk_measurement_is_emitted_only_once_per_turn(caplog):
    runner = runner_with_turn(VoiceTurn("question", "answer", True, False))

    def streamed(_session, _audio, _locale, play, _turn):
        play(b"first")
        play(b"second")
        return VoiceTurn("question", "answer", True, False)

    runner._client.turn.side_effect = streamed
    with (
        caplog.at_level("INFO", logger="kyrion-voice-satellite"),
        patch("kyrion_voice_satellite.dialogue.AlsaCapture"),
        patch(
            "kyrion_voice_satellite.dialogue.capture_utterance",
            side_effect=[Utterance(b"pcm", 5, "silence"), None],
        ),
    ):
        runner._run_session_once()
    assert caplog.text.count("event=satellite_first_chunk_received ") == 1
    assert caplog.text.count("event=satellite_chunk_received ") == 1
    assert runner._playback.play.call_args_list[1].args == (b"first",)
    assert runner._playback.play.call_args_list[2].args == (b"second",)
