from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "training" / "run_openwakeword_training.py"
SPEC = importlib.util.spec_from_file_location("run_openwakeword_training", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ScalarLike:
    def numel(self) -> int:
        return 1

    def item(self) -> float:
        return 7.0


def test_normalizes_scalar_tensor_like_rotation_index() -> None:
    assert MODULE.normalize_rotation_index(ScalarLike()) == 7


def test_preserves_plain_integer_rotation_index() -> None:
    assert MODULE.normalize_rotation_index(4) == 4
