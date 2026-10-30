"""Startup checks without downloading weights, CUDA or real voice recordings."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def runtime(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace())
    path = Path(__file__).parents[1] / "runtime/chatterbox_tts_server.py"
    spec = importlib.util.spec_from_file_location("chatterbox_startup_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def dependencies(monkeypatch, tmp_path):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"test fixture")
    monkeypatch.setenv("KYRION_CHATTERBOX_REFERENCE", str(reference))
    monkeypatch.delenv("KYRION_CHATTERBOX_MODEL_DIRECTORY", raising=False)
    loader = Mock(return_value=str(tmp_path / "cached-model"))
    model = Mock()
    factory = Mock(return_value=model)
    monkeypatch.setitem(
        sys.modules,
        "chatterbox.mtl_tts",
        SimpleNamespace(
            REPO_ID="reviewed/model",
            ChatterboxMultilingualTTS=SimpleNamespace(from_local=factory),
        ),
    )
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=loader))
    return loader, factory, model


def test_startup_uses_cached_weights_and_only_becomes_ready_after_warmup(monkeypatch, tmp_path):
    module = runtime(monkeypatch)
    loader, factory, model = dependencies(monkeypatch, tmp_path)
    assert module.health()["status"] == "loading"

    # Inspect readiness while warmup is executing, before publication.
    def warmup(*args, **kwargs):
        assert module.health()["status"] == "loading"

    model.generate.side_effect = warmup
    module.load_runtime()
    loader.assert_called_once_with(
        repo_id="reviewed/model",
        local_files_only=True,
        allow_patterns=module.MODEL_FILES,
    )
    factory.assert_called_once_with(tmp_path / "cached-model", device="cuda")
    assert module.health()["status"] == "ready"


def test_missing_cache_fails_without_network_fallback(monkeypatch, tmp_path):
    module = runtime(monkeypatch)
    loader, factory, _ = dependencies(monkeypatch, tmp_path)
    loader.side_effect = FileNotFoundError("cache unavailable")
    with pytest.raises(FileNotFoundError):
        module.load_runtime()
    factory.assert_not_called()
    assert module.health()["status"] == "loading"


def test_failed_warmup_never_publishes_ready_model(monkeypatch, tmp_path):
    module = runtime(monkeypatch)
    _, _, model = dependencies(monkeypatch, tmp_path)
    model.generate.side_effect = RuntimeError("CUDA unavailable")
    with pytest.raises(RuntimeError):
        module.load_runtime()
    assert module.health()["status"] == "loading"


def test_explicit_model_directory_avoids_cache_resolution(monkeypatch, tmp_path):
    module = runtime(monkeypatch)
    loader, factory, _ = dependencies(monkeypatch, tmp_path)
    monkeypatch.setenv("KYRION_CHATTERBOX_MODEL_DIRECTORY", str(tmp_path))
    module.load_runtime()
    loader.assert_not_called()
    factory.assert_called_once_with(tmp_path, device="cuda")
