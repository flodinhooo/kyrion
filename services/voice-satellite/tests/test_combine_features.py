from pathlib import Path
from runpy import run_path

SCRIPT = Path(__file__).parents[1] / "training" / "combine_features.py"
MODULE = run_path(str(SCRIPT))


def test_shuffled_sources_has_expected_members_and_is_deterministic() -> None:
    first = MODULE["shuffled_sources"](3, 2, 2)
    second = MODULE["shuffled_sources"](3, 2, 2)

    assert first == second
    assert sorted(first) == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 0), (1, 1), (1, 1)]
