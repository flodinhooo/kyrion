"""Run upstream openWakeWord training with narrowly scoped compatibility fixes."""

from __future__ import annotations

import argparse
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


def normalize_rotation_index(value: Any) -> Any:
    """Convert SpeechBrain's scalar tensor to its documented integer argument."""
    numel = getattr(value, "numel", None)
    item = getattr(value, "item", None)
    if callable(numel) and callable(item) and numel() == 1:
        return int(item())
    return value


def patch_speechbrain_convolution() -> None:
    from speechbrain.processing import signal_processing

    original: Callable[..., Any] = signal_processing.convolve1d
    original_reverberate: Callable[..., Any] = signal_processing.reverberate

    def compatible_convolve1d(*args: Any, **kwargs: Any) -> Any:
        if "rotation_index" in kwargs:
            kwargs["rotation_index"] = normalize_rotation_index(kwargs["rotation_index"])
        return original(*args, **kwargs)

    def mono_reverberate(waveforms: Any, rir_waveform: Any, *args: Any, **kwargs: Any) -> Any:
        # torchaudio returns [channels, time], while this wake-word pipeline is mono.
        # SpeechBrain cannot use its multi-element direct-index tensor as a slice.
        if getattr(rir_waveform, "ndim", 0) == 2 and rir_waveform.shape[0] > 1:
            rir_waveform = rir_waveform.mean(dim=0, keepdim=True)
        return original_reverberate(waveforms, rir_waveform, *args, **kwargs)

    signal_processing.convolve1d = compatible_convolve1d
    signal_processing.reverberate = mono_reverberate


def patch_false_string_defaults() -> None:
    """Correct upstream argparse defaults that use the truthy string ``False``."""
    original = argparse.ArgumentParser.add_argument

    def compatible_add_argument(parser: Any, *names: str, **kwargs: Any) -> Any:
        if kwargs.get("default") == "False":
            kwargs["default"] = False
        return original(parser, *names, **kwargs)

    argparse.ArgumentParser.add_argument = compatible_add_argument


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: run_openwakeword_training.py TRAIN.PY [arguments ...]")
    training_script = Path(sys.argv.pop(1)).resolve(strict=True)
    patch_speechbrain_convolution()
    patch_false_string_defaults()
    sys.argv[0] = str(training_script)
    runpy.run_path(str(training_script), run_name="__main__")


if __name__ == "__main__":
    main()
