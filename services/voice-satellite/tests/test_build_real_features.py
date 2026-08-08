from pathlib import Path
from runpy import run_path

import pytest

SCRIPT = Path(__file__).parents[1] / "training" / "build_real_features.py"
MODULE = run_path(str(SCRIPT))


def test_repeated_paths_is_stable(tmp_path: Path) -> None:
    (tmp_path / "b.wav").touch()
    (tmp_path / "a.wav").touch()

    assert MODULE["repeated_paths"](tmp_path, 2) == [
        str(tmp_path / "a.wav"),
        str(tmp_path / "a.wav"),
        str(tmp_path / "b.wav"),
        str(tmp_path / "b.wav"),
    ]


def test_repeated_paths_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No WAV clips"):
        MODULE["repeated_paths"](tmp_path, 2)
