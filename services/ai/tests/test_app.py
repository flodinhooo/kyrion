from kyrion_ai.app import app


def test_application_registers_model_and_chat_routes() -> None:
    paths = {route.path for route in app.routes}

    assert "/v1/models" in paths
    assert "/v1/models/benchmark" in paths
    assert "/v1/chat/stream" in paths
    assert "/v1/device-commands/propose" in paths
    assert "/v1/speech/transcribe" in paths
    assert "/v1/speech/synthesize" in paths
    assert "/v1/speech/resolve-response" in paths
