import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir


@dataclass(frozen=True, slots=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_allowed_models: tuple[str, ...]
    ollama_connect_timeout_seconds: float
    stt_model: str = "small"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    tts_provider: str = "http_batch"
    http_tts_url: str = "http://127.0.0.1:8020"
    # Compatibility only for existing explicit Qwen batch deployments.
    qwen_tts_url: str = "http://127.0.0.1:8010"
    xtts_experimental_enabled: bool = False
    xtts_tts_url: str = "http://127.0.0.1:8031"
    xtts_timeout_seconds: float = 120.0
    default_voice_id: str = "velora"
    piper_executable: str | None = None
    piper_model: str | None = None
    voice_response_manifest: Path = (
        Path(__file__).resolve().parents[2] / "voice-responses" / "manifest.json"
    )
    voice_response_cache_dir: Path = Path(gettempdir()) / "kyrion-voice-response-cache"
    voice_response_synthesis_revision: str = "configured-normal-tts-v1"

    @classmethod
    def from_environment(cls) -> "Settings":
        default_model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
        configured_models = tuple(
            model.strip()
            for model in os.getenv(
                "KYRION_ALLOWED_MODELS",
                "gemma3:1b,gemma3:4b,qwen3:8b",
            ).split(",")
            if model.strip()
        )
        allowed_models = tuple(dict.fromkeys((default_model, *configured_models)))
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=default_model,
            ollama_allowed_models=allowed_models,
            ollama_connect_timeout_seconds=float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "5")),
            stt_model=os.getenv("KYRION_STT_MODEL", "small"),
            stt_device=os.getenv("KYRION_STT_DEVICE", "cpu"),
            stt_compute_type=os.getenv("KYRION_STT_COMPUTE_TYPE", "int8"),
            tts_provider=os.getenv("KYRION_TTS_PROVIDER", "http_batch").lower(),
            http_tts_url=os.getenv("KYRION_HTTP_TTS_URL", "http://127.0.0.1:8020").rstrip("/"),
            qwen_tts_url=os.getenv("KYRION_QWEN_TTS_URL", "http://127.0.0.1:8010").rstrip("/"),
            xtts_experimental_enabled=os.getenv("KYRION_XTTS_EXPERIMENTAL_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            xtts_tts_url=os.getenv("KYRION_XTTS_TTS_URL", "http://127.0.0.1:8031").rstrip("/"),
            xtts_timeout_seconds=float(os.getenv("KYRION_XTTS_TIMEOUT_SECONDS", "120")),
            default_voice_id=os.getenv("KYRION_DEFAULT_VOICE_ID", "velora"),
            piper_executable=os.getenv("KYRION_PIPER_EXECUTABLE"),
            piper_model=os.getenv("KYRION_PIPER_MODEL"),
            voice_response_manifest=Path(
                os.getenv(
                    "KYRION_VOICE_RESPONSE_MANIFEST",
                    str(Path(__file__).resolve().parents[2] / "voice-responses" / "manifest.json"),
                )
            ),
            voice_response_cache_dir=Path(
                os.getenv(
                    "KYRION_VOICE_RESPONSE_CACHE_DIR",
                    str(Path(gettempdir()) / "kyrion-voice-response-cache"),
                )
            ),
            voice_response_synthesis_revision=os.getenv(
                "KYRION_VOICE_RESPONSE_SYNTHESIS_REVISION",
                "configured-normal-tts-v1",
            ),
        )
