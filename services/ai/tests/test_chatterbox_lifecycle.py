"""HTTP lifecycle regressions; real audio acceptance is recorded separately."""

import threading
from unittest.mock import Mock

from fastapi.testclient import TestClient
from test_chatterbox_startup import runtime


def test_http_liveness_remains_available_during_model_initialization(monkeypatch):
    module = runtime(monkeypatch)
    entered = threading.Event()
    release = threading.Event()

    def load():
        entered.set()
        release.wait(5)

    monkeypatch.setattr(module, "load_runtime", load)
    try:
        with TestClient(module.app) as client:
            assert entered.wait(2)
            assert client.get("/live").json() == {"status": "ok"}
            assert client.get("/health").json()["status"] == "loading"
            assert client.get("/ready").status_code == 503
            response = client.post("/v1/synthesize", json={"text": "Hallo", "voiceId": "velora"})
            assert response.status_code == 503
            assert response.json()["detail"] == "TTS_LOADING"
    finally:
        release.set()


def test_transient_initialization_failure_retries_with_bounded_backoff(monkeypatch):
    module = runtime(monkeypatch)
    loader = Mock(side_effect=[OSError("transient I/O"), OSError("transient I/O"), None])
    monkeypatch.setattr(module, "load_runtime", loader)
    stop = Mock()
    stop.is_set.return_value = False
    stop.wait.return_value = False
    module.initialize_with_retry(stop)
    assert loader.call_count == 3
    assert [call.args[0] for call in stop.wait.call_args_list] == [5, 10]
    assert module.startup_error is None


def test_permanent_failure_stays_live_but_reports_sanitized_readiness_error(monkeypatch):
    module = runtime(monkeypatch)
    loader = Mock(side_effect=FileNotFoundError("private/path/token"))
    monkeypatch.setattr(module, "load_runtime", loader)
    with TestClient(module.app) as client:
        # The startup worker completes quickly, but still runs concurrently.
        for _ in range(100):
            response = client.get("/ready")
            if response.json()["status"] == "error":
                break
        assert client.get("/live").status_code == 200
        assert response.status_code == 503
        assert response.json()["code"] == "TTS_MODEL_CACHE_MISSING"
        assert "private" not in response.text
    assert loader.call_count == 1


def test_ready_model_and_invalid_voice_contract(monkeypatch):
    module = runtime(monkeypatch)
    monkeypatch.setattr(module, "load_runtime", lambda: None)
    monkeypatch.setattr(module, "model", Mock())
    with TestClient(module.app) as client:
        assert client.get("/ready").status_code == 200
        assert client.get("/v1/voices").json()["defaultVoiceId"] == "velora"
        assert (
            client.post("/v1/synthesize", json={"text": "Hallo", "voiceId": "unknown"}).status_code
            == 400
        )
        assert (
            client.post("/v1/synthesize", json={"text": "", "voiceId": "velora"}).status_code == 422
        )
    module.model.generate.assert_not_called()
