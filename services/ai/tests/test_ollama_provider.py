import asyncio

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatRequest
from kyrion_ai.providers.ollama import OllamaProvider


def test_unreachable_ollama_returns_stable_error() -> None:
    provider = OllamaProvider(
        Settings(
            ollama_base_url="http://127.0.0.1:1",
            ollama_model="test-model",
            ollama_allowed_models=("test-model",),
            ollama_connect_timeout_seconds=0.1,
        )
    )
    request = ChatRequest.model_validate(
        {"messages": [{"role": "user", "content": "Hallo"}], "locale": "de"}
    )

    async def collect_events() -> list[str | None]:
        return [event.code async for event in provider.stream_chat(request)]

    assert asyncio.run(collect_events()) == ["MODEL_UNAVAILABLE"]
