import asyncio
import json
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatEvent, ChatRequest, ModelCatalog, ModelInfo


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

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        message_id = str(uuid4())
        timeout = httpx.Timeout(
            connect=self._settings.ollama_connect_timeout_seconds,
            read=None,
            write=30.0,
            pool=5.0,
        )
        payload = {
            "model": request.model_id or self._settings.ollama_model,
            "messages": [message.model_dump() for message in request.messages],
            "stream": True,
        }

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


def _context_length(model_info: dict[str, int | float | str | bool | None]) -> int | None:
    for key, value in model_info.items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    return None
