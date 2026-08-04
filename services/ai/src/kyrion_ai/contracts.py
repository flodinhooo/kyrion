from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=100_000)


class MemoryContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    category: Literal["preference", "person", "project", "value", "other"]
    content: str = Field(min_length=1, max_length=1_000)
    sensitivity: Literal["standard", "sensitive"]


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
    memory_context: list[MemoryContextItem] = Field(
        default_factory=list,
        alias="memoryContext",
        max_length=3,
    )
    locale: Literal["de", "en"]


class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    size_bytes: int = Field(serialization_alias="sizeBytes")
    parameter_size: str = Field(serialization_alias="parameterSize")
    quantization: str
    capabilities: list[str]
    context_length: int | None = Field(default=None, serialization_alias="contextLength")


class ModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_model_id: str = Field(serialization_alias="defaultModelId")
    models: list[ModelInfo]


class ModelBenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(alias="modelId", min_length=1, max_length=128)
    locale: Literal["de", "en"]


class BenchmarkPromptMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(serialization_alias="promptId")
    duration_ms: float = Field(serialization_alias="durationMs", ge=0)
    generated_tokens: int = Field(serialization_alias="generatedTokens", ge=0)
    tokens_per_second: float = Field(serialization_alias="tokensPerSecond", ge=0)
    passed: bool


class ModelBenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(serialization_alias="modelId")
    warmup_load_ms: float = Field(serialization_alias="warmupLoadMs", ge=0)
    average_duration_ms: float = Field(serialization_alias="averageDurationMs", ge=0)
    average_tokens_per_second: float = Field(
        serialization_alias="averageTokensPerSecond",
        ge=0,
    )
    checks_passed: int = Field(serialization_alias="checksPassed", ge=0)
    prompt_count: int = Field(serialization_alias="promptCount", ge=1)
    prompts: list[BenchmarkPromptMetric]


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
