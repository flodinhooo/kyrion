from kyrion_ai.config import Settings


def test_settings_include_default_model_once_in_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setenv("KYRION_ALLOWED_MODELS", "gemma3:4b,qwen3:8b,gemma3:4b")

    settings = Settings.from_environment()

    assert settings.ollama_model == "qwen3:8b"
    assert settings.ollama_allowed_models == ("qwen3:8b", "gemma3:4b")
    assert settings.tts_provider == "http_batch"
    assert settings.http_tts_url == "http://127.0.0.1:8020"
    assert settings.xtts_experimental_enabled is False
    assert settings.xtts_tts_url == "http://127.0.0.1:8031"
