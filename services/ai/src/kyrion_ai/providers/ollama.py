import json
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatEvent, ChatRequest


class OllamaProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model(self) -> str:
        return self._settings.ollama_model

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        message_id = str(uuid4())
        timeout = httpx.Timeout(
            connect=self._settings.ollama_connect_timeout_seconds,
            read=None,
            write=30.0,
            pool=5.0,
        )
        payload = {
            "model": self._settings.ollama_model,
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
