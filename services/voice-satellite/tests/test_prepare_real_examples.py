from pathlib import Path
from runpy import run_path

SCRIPT = Path(__file__).parents[1] / "training" / "prepare_real_examples.py"
MODULE = run_path(str(SCRIPT))


def test_holdout_is_deterministic_and_spread_across_order() -> None:
    assert [number for number in range(1, 13) if MODULE["is_holdout"](number)] == [2, 7, 12]
