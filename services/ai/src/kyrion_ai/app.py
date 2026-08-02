from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatRequest
from kyrion_ai.providers.ollama import OllamaProvider

settings = Settings.from_environment()
provider = OllamaProvider(settings)

app = FastAPI(title="Kyrion AI", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": "ollama", "model": provider.model}


@app.post("/v1/chat/stream", response_class=StreamingResponse)
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    async def events() -> AsyncIterator[bytes]:
        async for event in provider.stream_chat(request):
            yield event.to_ndjson()

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
