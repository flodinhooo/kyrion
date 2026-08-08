from pathlib import Path
from runpy import run_path

SCRIPT = Path(__file__).parents[1] / "training" / "label_recording.py"
MODULE = run_path(str(SCRIPT))


def test_parse_numbers() -> None:
    assert MODULE["parse_numbers"]("7, 10,18") == {7, 10, 18}
    assert MODULE["parse_numbers"]("") == set()
