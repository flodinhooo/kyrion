from pathlib import Path
from runpy import run_path

SCRIPT = Path(__file__).parents[1] / "training" / "segment_recording.py"
MODULE = run_path(str(SCRIPT))


def test_find_segments_merges_short_gaps_and_removes_short_noise() -> None:
    levels = [0.0] * 5 + [0.5] * 4 + [0.0] * 2 + [0.5] * 4 + [0.0] * 8 + [0.5]

    segments = MODULE["find_segments"](
        levels,
        frame_seconds=0.1,
        threshold=0.1,
        max_gap_seconds=0.3,
        min_speech_seconds=0.3,
    )

    assert [(segment.start_frame, segment.end_frame) for segment in segments] == [(5, 15)]


def test_percentile_is_deterministic() -> None:
    assert MODULE["percentile"]([4.0, 1.0, 3.0, 2.0], 0.5) == 3.0
