from __future__ import annotations


class WebRtcVoiceActivityDetector:
    """Apply WebRTC VAD to the satellite's 80 ms PCM frames."""

    def __init__(self, aggressiveness: int = 2) -> None:
        if aggressiveness not in range(4):
            raise ValueError("VAD aggressiveness must be between 0 and 3")
        try:
            import webrtcvad
        except ImportError as error:
            raise RuntimeError("WebRTC VAD runtime is not installed") from error
        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes) -> bool:
        chunk_bytes = 640  # 20 ms of mono PCM16 at 16 kHz.
        if len(frame) % chunk_bytes != 0:
            raise ValueError("VAD input must contain complete 20 ms PCM frames")
        return any(
            self._vad.is_speech(frame[offset : offset + chunk_bytes], 16_000)
            for offset in range(0, len(frame), chunk_bytes)
        )
