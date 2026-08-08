from __future__ import annotations

from pathlib import Path


class OpenWakeWordDetector:
    def __init__(self, model_path: Path) -> None:
        if not model_path.is_file() or model_path.suffix != ".onnx":
            raise ValueError("Wake-word model must be an existing ONNX file")
        try:
            import numpy as np
            from openwakeword.model import Model
        except ImportError as error:
            raise RuntimeError("OpenWakeWord ONNX runtime is not installed") from error
        self._np = np
        self._model = Model(wakeword_models=[str(model_path)], inference_framework="onnx")

    def score(self, frame: bytes) -> float:
        samples = self._np.frombuffer(frame, dtype=self._np.int16)
        predictions = self._model.predict(samples)
        return max((float(value) for value in predictions.values()), default=0.0)
