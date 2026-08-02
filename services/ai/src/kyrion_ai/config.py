import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_allowed_models: tuple[str, ...]
    ollama_connect_timeout_seconds: float

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
        )
