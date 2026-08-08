from kyrion_voice_satellite.runtime import listen


class FakeDetector:
    def __init__(self, scores: list[float]) -> None:
        self.scores = iter(scores)

    def score(self, _frame: bytes) -> float:
        return next(self.scores)


def test_listener_applies_threshold_and_cooldown() -> None:
    detections: list[float] = []
    times = iter([0.0, 1.0, 1.5, 3.1])

    listen(
        [b"a", b"b", b"c", b"d"], FakeDetector([0.2, 0.8, 0.9, 0.7]),
        0.5, 2.0, detections.append, monotonic=lambda: next(times),
    )

    assert detections == [0.8, 0.7]
