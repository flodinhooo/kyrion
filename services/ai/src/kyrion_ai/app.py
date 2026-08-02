from collections.abc import AsyncIterator

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, StreamingResponse

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatRequest
from kyrion_ai.prompts import prepare_chat_request
from kyrion_ai.providers.ollama import OllamaProvider

settings = Settings.from_environment()
provider = OllamaProvider(settings)

app = FastAPI(title="Kyrion AI", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": "ollama", "model": provider.model}


@app.get("/v1/models")
async def list_models() -> dict[str, str | list[dict[str, str]]]:
    return {
        "defaultModelId": provider.model,
        "models": [{"id": model, "label": model} for model in provider.models],
    }


@app.post("/v1/chat/stream", response_class=StreamingResponse)
async def stream_chat(request: ChatRequest) -> Response:
    if request.model_id is not None and not provider.supports_model(request.model_id):
        return JSONResponse({"code": "INVALID_REQUEST"}, status_code=400)

    prepared_request = prepare_chat_request(request)

    async def events() -> AsyncIterator[bytes]:
        async for event in provider.stream_chat(prepared_request):
            yield event.to_ndjson()

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
