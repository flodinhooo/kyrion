from kyrion_voice_satellite.audio import FRAME_BYTES
from kyrion_voice_satellite.utterance import capture_utterance

FRAME = bytes(FRAME_BYTES)


class SequenceVad:
    def __init__(self, values: list[bool]) -> None:
        self.values = iter(values)

    def is_speech(self, frame: bytes) -> bool:
        return next(self.values)


def test_capture_waits_for_speech_and_stops_after_bounded_silence() -> None:
    result = capture_utterance(
        [FRAME] * 7,
        SequenceVad([False, False, True, True, True, False, False]),
        start_timeout_seconds=1,
        end_silence_seconds=0.16,
        max_seconds=2,
    )

    assert result is not None
    assert result.speech_frames == 3
    assert result.ended_by == "silence"
    assert len(result.pcm) == FRAME_BYTES * 5


def test_capture_returns_none_when_no_speech_starts() -> None:
    result = capture_utterance(
        [FRAME] * 3,
        SequenceVad([False, False, False]),
        start_timeout_seconds=0.24,
        end_silence_seconds=0.16,
        max_seconds=2,
    )

    assert result is None


def test_capture_enforces_maximum_duration() -> None:
    result = capture_utterance(
        [FRAME] * 4,
        SequenceVad([True] * 4),
        start_timeout_seconds=1,
        end_silence_seconds=0.16,
        max_seconds=0.24,
    )

    assert result is not None
    assert result.ended_by == "maximum"
    assert len(result.pcm) == FRAME_BYTES * 3
