from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=100_000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(
        default=None,
        alias="conversationId",
        min_length=1,
        max_length=128,
    )
    model_id: str | None = Field(default=None, alias="modelId", min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(min_length=1, max_length=200)
    locale: Literal["de", "en"]


ChatErrorCode = Literal[
    "MODEL_UNAVAILABLE",
    "REQUEST_ABORTED",
    "INVALID_REQUEST",
    "STREAM_FAILED",
]


class ChatEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["message.started", "message.delta", "message.completed", "error"]
    message_id: str | None = Field(default=None, serialization_alias="messageId")
    delta: str | None = None
    code: ChatErrorCode | None = None

    def to_ndjson(self) -> bytes:
        return self.model_dump_json(by_alias=True, exclude_none=True).encode() + b"\n"
