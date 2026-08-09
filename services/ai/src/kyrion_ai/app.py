import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from kyrion_ai.config import Settings
from kyrion_ai.contracts import (
    ChatRequest,
    DeviceCommandProposalRequest,
    DeviceCommandProposalResponse,
    ModelBenchmarkRequest,
    ModelBenchmarkResult,
    ModelCatalog,
)
from kyrion_ai.device_commands import propose_device_command
from kyrion_ai.prompts import prepare_chat_request
from kyrion_ai.providers.ollama import OllamaProvider
from kyrion_ai.speech import InvalidAudioError, SpeechService, SpeechUnavailableError

settings = Settings.from_environment()
provider = OllamaProvider(settings)
speech = SpeechService(settings)
logger = logging.getLogger("kyrion-ai")

app = FastAPI(title="Kyrion AI", version="0.1.0")


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
    locale: str = Field(pattern="^(de|en)$")
    voice_id: str | None = Field(default=None, alias="voiceId", pattern="^[a-z0-9_-]{1,40}$")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": "ollama", "model": provider.model}


@app.post("/v1/speech/transcribe")
async def transcribe(request: Request) -> Response:
    if request.headers.get("content-type") != "audio/wav":
        return JSONResponse({"code": "INVALID_AUDIO"}, status_code=415)
    locale = request.headers.get("x-kyrion-locale", "de")
    if locale not in {"de", "en"}:
        return JSONResponse({"code": "INVALID_REQUEST"}, status_code=400)
    audio = await request.body()
    if not 44 <= len(audio) <= 1_000_000:
        logger.warning(
            "Rejected speech container length=%d header=%s", len(audio), audio[:12].hex()
        )
        return JSONResponse({"code": "INVALID_AUDIO"}, status_code=400)
    try:
        text = await run_in_threadpool(speech.transcribe, audio, locale)
    except InvalidAudioError:
        logger.warning(
            "Rejected speech WAV structure length=%d header=%s", len(audio), audio[:12].hex()
        )
        return JSONResponse({"code": "INVALID_AUDIO"}, status_code=400)
    except SpeechUnavailableError:
        return JSONResponse({"code": "STT_UNAVAILABLE"}, status_code=503)
    return JSONResponse({"text": text, "locale": locale})


@app.post("/v1/speech/synthesize")
async def synthesize(request: SynthesisRequest) -> Response:
    try:
        audio = await run_in_threadpool(speech.synthesize, request.text, request.voice_id)
    except SpeechUnavailableError:
        return JSONResponse({"code": "TTS_UNAVAILABLE"}, status_code=503)
    return Response(
        audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/v1/speech/voices")
async def voices() -> Response:
    try:
        catalog = await run_in_threadpool(speech.voices)
    except SpeechUnavailableError:
        return JSONResponse({"code": "TTS_UNAVAILABLE"}, status_code=503)
    return JSONResponse(catalog)


@app.get("/v1/models", response_model=ModelCatalog, response_model_by_alias=True)
async def list_models() -> ModelCatalog:
    return await provider.list_models()


@app.post(
    "/v1/models/benchmark",
    response_model=ModelBenchmarkResult,
    response_model_by_alias=True,
)
async def benchmark_model(request: ModelBenchmarkRequest) -> ModelBenchmarkResult | Response:
    if not provider.supports_model(request.model_id):
        return JSONResponse({"code": "INVALID_REQUEST"}, status_code=400)
    return await provider.benchmark_model(request)


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


@app.post(
    "/v1/device-commands/propose",
    response_model=DeviceCommandProposalResponse,
    response_model_by_alias=True,
    response_model_exclude_none=True,
)
async def propose_command(request: DeviceCommandProposalRequest) -> DeviceCommandProposalResponse:
    return DeviceCommandProposalResponse(proposal=propose_device_command(request))
