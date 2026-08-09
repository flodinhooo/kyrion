from __future__ import annotations

import logging
from enum import Enum

from kyrion_voice_satellite.audio import AlsaCapture
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient
from kyrion_voice_satellite.playback import PipeWirePlayback
from kyrion_voice_satellite.utterance import capture_utterance
from kyrion_voice_satellite.vad import WebRtcVoiceActivityDetector
from kyrion_voice_satellite.wav import pcm_to_wav

LOGGER = logging.getLogger("kyrion-voice-satellite")


class DialogueState(Enum):
    IDLE = "idle"
    ACKNOWLEDGING = "acknowledging"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    CLOSING = "closing"


class DialogueRunner:
    def __init__(self, config: SatelliteConfig) -> None:
        if not config.dialogue_enabled:
            raise ValueError("Dialogue configuration is disabled")
        assert config.core_url and config.satellite_id and config.credential_file
        self._config = config
        self._client = CoreVoiceClient(
            config.core_url, config.satellite_id, config.credential_file,
        )
        self._vad = WebRtcVoiceActivityDetector()
        self._playback = PipeWirePlayback(config.playback_target)
        self._greeting_audio = (
            config.greeting_audio_file.read_bytes() if config.greeting_audio_file else None
        )
        self.state = DialogueState.IDLE

    def run_session(self) -> None:
        session = self._client.open_session()
        reason = "error"
        try:
            if self._greeting_audio is not None:
                self.state = DialogueState.ACKNOWLEDGING
                self._playback.play(self._greeting_audio)
            while True:
                self.state = DialogueState.LISTENING
                utterance = capture_utterance(
                    AlsaCapture(self._config.capture_device).frames(),
                    self._vad,
                    start_timeout_seconds=self._config.speech_start_timeout_seconds,
                    end_silence_seconds=self._config.speech_end_silence_seconds,
                    max_seconds=self._config.utterance_max_seconds,
                )
                if utterance is None:
                    reason = "inactivity"
                    return
                self.state = DialogueState.PROCESSING
                self.state = DialogueState.SPEAKING
                turn = self._client.turn(
                    session.id,
                    pcm_to_wav(utterance.pcm),
                    self._config.locale,
                    self._playback.play,
                )
                LOGGER.info("Voice turn transcribed and answered")
                if not turn.continue_session:
                    reason = "explicit"
                    return
        finally:
            self.state = DialogueState.CLOSING
            if reason != "explicit":
                self._client.close_session(session.id, reason)
            self.state = DialogueState.IDLE
