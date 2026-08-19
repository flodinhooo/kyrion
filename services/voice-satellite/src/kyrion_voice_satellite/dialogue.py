from __future__ import annotations

import logging
import time
import uuid
from enum import Enum

from kyrion_voice_satellite.audio import AlsaCapture
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient, CoreVoiceError
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
        self._legacy_greeting_audio = (
            config.greeting_audio_file.read_bytes() if config.greeting_audio_file else None
        )
        self.state = DialogueState.IDLE

    def run_session(self) -> None:
        while self._run_session_once():
            LOGGER.info("Wake word repeated; opening a fresh voice session")

    def _run_session_once(self) -> bool:
        session = self._client.open_session()
        reason = "error"
        try:
            self.state = DialogueState.ACKNOWLEDGING
            try:
                greeting_audio = self._client.greeting(session.id, self._config.locale)
            except CoreVoiceError:
                if self._legacy_greeting_audio is None:
                    raise
                LOGGER.warning("Using configured legacy greeting after Core greeting failure")
                greeting_audio = self._legacy_greeting_audio
            self._playback.play(greeting_audio)
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
                    return False
                self.state = DialogueState.PROCESSING
                turn_id = str(uuid.uuid4())
                speech_end = time.time_ns() // 1_000_000
                LOGGER.info("[VOICE] turn=%s event=speech_end ts_ms=%d", turn_id, speech_end)

                def play_chunk(audio: bytes, voice_turn_id: str = turn_id) -> None:
                    received = time.time_ns() // 1_000_000
                    LOGGER.info(
                        "[VOICE] turn=%s event=satellite_first_chunk_received ts_ms=%d",
                        voice_turn_id,
                        received,
                    )
                    LOGGER.info(
                        "[VOICE] turn=%s event=playback_started ts_ms=%d",
                        voice_turn_id,
                        time.time_ns() // 1_000_000,
                    )
                    self._playback.play(audio)

                self.state = DialogueState.SPEAKING
                turn = self._client.turn(
                    session.id,
                    pcm_to_wav(utterance.pcm),
                    self._config.locale,
                    play_chunk,
                    turn_id,
                )
                LOGGER.info("Voice turn transcribed and answered")
                if turn.restart_session:
                    reason = "explicit"
                    return True
                if not turn.continue_session:
                    reason = "explicit"
                    return False
        finally:
            self.state = DialogueState.CLOSING
            if reason != "explicit":
                self._client.close_session(session.id, reason)
            self.state = DialogueState.IDLE
        return False
