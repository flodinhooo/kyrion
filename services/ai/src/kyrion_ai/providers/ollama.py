import asyncio
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from kyrion_ai.benchmarks import benchmark_prompts, response_passes
from kyrion_ai.config import Settings
from kyrion_ai.contracts import (
    BenchmarkPromptMetric,
    ChatEvent,
    ChatRequest,
    ModelBenchmarkRequest,
    ModelBenchmarkResult,
    ModelCatalog,
    ModelInfo,
)


class _OllamaModelDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")

    parameter_size: str = "unknown"
    quantization_level: str = "unknown"


class _OllamaModelTag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    model: str
    size: int = Field(ge=0)
    details: _OllamaModelDetails


class _OllamaModelList(BaseModel):
    model_config = ConfigDict(extra="ignore")

    models: list[_OllamaModelTag]


class _OllamaModelShow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    capabilities: list[str] = Field(default_factory=list)
    model_info: dict[str, int | float | str | bool | None] = Field(
        default_factory=dict
    )


class _OllamaChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = ""


class _OllamaChatResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: _OllamaChatMessage
    total_duration: int = Field(default=0, ge=0)
    load_duration: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)
    eval_duration: int = Field(default=0, ge=0)


class OllamaProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model(self) -> str:
        return self._settings.ollama_model

    @property
    def models(self) -> tuple[str, ...]:
        return self._settings.ollama_allowed_models

    def supports_model(self, model_id: str) -> bool:
        return model_id in self.models

    async def list_models(self) -> ModelCatalog:
        timeout = httpx.Timeout(self._settings.ollama_connect_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{self._settings.ollama_base_url}/api/tags")
            response.raise_for_status()
            installed = _OllamaModelList.model_validate(response.json())

            allowed = [
                model
                for model_id in self.models
                for model in installed.models
                if model.model == model_id or model.name == model_id
            ]
            details = await asyncio.gather(
                *(self._show_model(client, model.model) for model in allowed)
            )

        return ModelCatalog(
            default_model_id=self.model,
            models=[
                ModelInfo(
                    id=model.model,
                    label=model.model,
                    size_bytes=model.size,
                    parameter_size=model.details.parameter_size,
                    quantization=model.details.quantization_level,
                    capabilities=show.capabilities,
                    context_length=_context_length(show.model_info),
                )
                for model, show in zip(allowed, details, strict=True)
            ],
        )

    async def _show_model(
        self,
        client: httpx.AsyncClient,
        model_id: str,
    ) -> _OllamaModelShow:
        try:
            response = await client.post(
                f"{self._settings.ollama_base_url}/api/show",
                json={"model": model_id, "verbose": False},
            )
            response.raise_for_status()
            return _OllamaModelShow.model_validate(response.json())
        except (httpx.HTTPError, ValueError):
            return _OllamaModelShow()

    async def benchmark_model(
        self,
        request: ModelBenchmarkRequest,
    ) -> ModelBenchmarkResult:
        timeout = httpx.Timeout(
            connect=self._settings.ollama_connect_timeout_seconds,
            read=120.0,
            write=30.0,
            pool=5.0,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            warmup = await self._run_benchmark_prompt(
                client,
                request.model_id,
                "Reply with OK.",
                max_tokens=4,
            )
            metrics = []
            for prompt in benchmark_prompts(request.locale):
                result = await self._run_benchmark_prompt(
                    client,
                    request.model_id,
                    prompt.content,
                    max_tokens=96,
                )
                metrics.append(
                    BenchmarkPromptMetric(
                        prompt_id=prompt.id,
                        duration_ms=_nanoseconds_to_milliseconds(result.total_duration),
                        generated_tokens=result.eval_count,
                        tokens_per_second=_tokens_per_second(result),
                        passed=response_passes(prompt, result.message.content),
                    )
                )

        return ModelBenchmarkResult(
            model_id=request.model_id,
            warmup_load_ms=_nanoseconds_to_milliseconds(warmup.load_duration),
            average_duration_ms=_average([metric.duration_ms for metric in metrics]),
            average_tokens_per_second=_average(
                [metric.tokens_per_second for metric in metrics]
            ),
            checks_passed=sum(metric.passed for metric in metrics),
            prompt_count=len(metrics),
            prompts=metrics,
        )

    async def _run_benchmark_prompt(
        self,
        client: httpx.AsyncClient,
        model_id: str,
        prompt: str,
        *,
        max_tokens: int,
    ) -> _OllamaChatResult:
        response = await client.post(
            f"{self._settings.ollama_base_url}/api/chat",
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "keep_alive": "5m",
                "options": {
                    "temperature": 0,
                    "seed": 42,
                    "num_predict": max_tokens,
                },
            },
        )
        response.raise_for_status()
        return _OllamaChatResult.model_validate(response.json())

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        message_id = str(uuid4())
        timeout = httpx.Timeout(
            connect=self._settings.ollama_connect_timeout_seconds,
            read=None,
            write=30.0,
            pool=5.0,
        )
        payload = _chat_payload(request, self._settings.ollama_model)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client, client.stream(
                "POST",
                f"{self._settings.ollama_base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                yield ChatEvent(type="message.started", message_id=message_id)

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        yield ChatEvent(type="error", code="STREAM_FAILED")
                        return
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield ChatEvent(
                            type="message.delta",
                            message_id=message_id,
                            delta=content,
                        )
                    if chunk.get("done"):
                        yield ChatEvent(type="message.completed", message_id=message_id)
                        return
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.HTTPStatusError):
            yield ChatEvent(type="error", code="MODEL_UNAVAILABLE")
        except (httpx.HTTPError, json.JSONDecodeError):
            yield ChatEvent(type="error", code="STREAM_FAILED")


def _chat_payload(request: ChatRequest, default_model: str) -> dict[str, object]:
    voice_mode = request.interaction_mode == "voice"
    return {
        "model": request.model_id or default_model,
        "messages": [message.model_dump() for message in request.messages],
        "stream": True,
        # Reasoning-capable models otherwise finish an invisible thinking pass
        # before emitting their user-facing answer.
        "think": False,
        "keep_alive": "24h" if voice_mode else "10m",
        # 128 tokens leave room for a natural two-to-four-sentence spoken answer
        # while retaining a firm bound for local latency and resource use.
        "options": {"num_ctx": 4096, **({"num_predict": 128} if voice_mode else {})},
    }


def _context_length(model_info: dict[str, int | float | str | bool | None]) -> int | None:
    for key, value in model_info.items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    return None


def _nanoseconds_to_milliseconds(value: int) -> float:
    return round(value / 1_000_000, 1)


def _tokens_per_second(result: _OllamaChatResult) -> float:
    if result.eval_duration == 0:
        return 0.0
    return round(result.eval_count / (result.eval_duration / 1_000_000_000), 1)


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0
