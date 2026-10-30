from collections.abc import AsyncIterator
from typing import Protocol

from kyrion_ai.contracts import ChatEvent, ChatRequest
from kyrion_ai.model_contracts import ModelProfile


class LanguageModelProvider(Protocol):
    def stream_chat(
        self, request: ChatRequest, profile: ModelProfile
    ) -> AsyncIterator[ChatEvent]: ...
