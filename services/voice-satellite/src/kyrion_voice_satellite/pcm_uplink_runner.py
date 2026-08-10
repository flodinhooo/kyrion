from __future__ import annotations

import logging
import time
import uuid
from itertools import islice

from kyrion_voice_satellite.audio import AlsaCapture
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient
from kyrion_voice_satellite.pcm_uplink import PcmUplinkClient
from kyrion_voice_satellite.utterance import FRAME_SECONDS

LOGGER = logging.getLogger("kyrion-voice-satellite")


class PcmUplinkRunner:
    def __init__(self, config: SatelliteConfig) -> None:
        if not config.dialogue_enabled:
            raise ValueError("Dialogue configuration is disabled")
        assert config.core_url and config.satellite_id and config.credential_file
        self._config = config
        self._sessions = CoreVoiceClient(
            config.core_url, config.satellite_id, config.credential_file,
        )

    def run_session(self) -> None:
        session = self._sessions.open_session()
        turn_id = str(uuid.uuid4())
        uplink = PcmUplinkClient(
            self._config.core_url,
            self._config.satellite_id,
            self._config.credential_file,
            epoch_millis=lambda: time.time_ns() // 1_000_000 + session.clock_offset_millis,
        )
        reason = "error"
        frames = AlsaCapture(self._config.capture_device).frames()
        frame_limit = round(self._config.utterance_max_seconds / FRAME_SECONDS)
        try:
            result = uplink.stream(
                session.id, turn_id, islice(frames, frame_limit),
            )
            reason = "maximum"
            LOGGER.info(
                "[VOICE] turn=%s event=pcm_uplink_complete frames=%d bytes=%d "
                "first_latency_ms=%s maximum_latency_ms=%s",
                turn_id,
                result.frames_received,
                result.pcm_bytes_received,
                result.first_frame_latency_millis,
                result.maximum_frame_latency_millis,
            )
        finally:
            frames.close()
            self._sessions.close_session(session.id, reason)
