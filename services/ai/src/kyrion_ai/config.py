import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_allowed_models: tuple[str, ...]
    ollama_connect_timeout_seconds: float
    stt_model: str = "small"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    piper_executable: str | None = None
    piper_model: str | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        default_model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
        configured_models = tuple(
            model.strip()
            for model in os.getenv(
                "KYRION_ALLOWED_MODELS",
                "gemma3:4b,qwen3:8b",
            ).split(",")
            if model.strip()
        )
        allowed_models = tuple(dict.fromkeys((default_model, *configured_models)))
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=default_model,
            ollama_allowed_models=allowed_models,
            ollama_connect_timeout_seconds=float(
                os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "5")
            ),
            stt_model=os.getenv("KYRION_STT_MODEL", "small"),
            stt_device=os.getenv("KYRION_STT_DEVICE", "cpu"),
            stt_compute_type=os.getenv("KYRION_STT_COMPUTE_TYPE", "int8"),
            piper_executable=os.getenv("KYRION_PIPER_EXECUTABLE"),
            piper_model=os.getenv("KYRION_PIPER_MODEL"),
        )
