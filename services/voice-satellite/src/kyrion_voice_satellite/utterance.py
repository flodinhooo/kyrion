from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from kyrion_voice_satellite.audio import FRAME_BYTES

FRAME_SECONDS = 0.08


class VoiceActivityDetector(Protocol):
    def is_speech(self, frame: bytes) -> bool: ...


@dataclass(frozen=True, slots=True)
class Utterance:
    pcm: bytes
    speech_frames: int
    ended_by: str


def capture_utterance(
    frames: Iterable[bytes],
    detector: VoiceActivityDetector,
    *,
    start_timeout_seconds: float,
    end_silence_seconds: float,
    max_seconds: float,
) -> Utterance | None:
    start_limit = round(start_timeout_seconds / FRAME_SECONDS)
    silence_limit = round(end_silence_seconds / FRAME_SECONDS)
    maximum = round(max_seconds / FRAME_SECONDS)
    buffered: list[bytes] = []
    speech_frames = 0
    trailing_silence = 0
    started = False

    for index, frame in enumerate(frames):
        if len(frame) != FRAME_BYTES:
            raise ValueError("Capture returned an invalid PCM frame")
        speech = detector.is_speech(frame)
        if not started:
            if not speech:
                if index + 1 >= start_limit:
                    return None
                continue
            started = True

        buffered.append(frame)
        if speech:
            speech_frames += 1
            trailing_silence = 0
        else:
            trailing_silence += 1
            if trailing_silence >= silence_limit:
                return Utterance(b"".join(buffered), speech_frames, "silence")
        if len(buffered) >= maximum:
            return Utterance(b"".join(buffered), speech_frames, "maximum")
    return Utterance(b"".join(buffered), speech_frames, "capture-ended") if buffered else None
