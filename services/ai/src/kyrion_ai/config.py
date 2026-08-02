import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_connect_timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
            ollama_connect_timeout_seconds=float(
                os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "5")
            ),
        )
