from collections.abc import AsyncIterator
from typing import Protocol

from kyrion_ai.contracts import ChatEvent, ChatRequest


class LanguageModelProvider(Protocol):
    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]: ...
