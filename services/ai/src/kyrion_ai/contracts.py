from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    interaction_mode: Literal["chat", "voice"] = Field(default="chat", alias="interactionMode")
    voice_turn_id: str | None = Field(default=None, alias="voiceTurnId", max_length=64)


class RuntimeDeviceCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)


class RuntimeDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=60)
    display_name: str = Field(alias="displayName", min_length=1, max_length=160)
    room_name: str | None = Field(default=None, alias="roomName", max_length=120)
    capabilities: list[RuntimeDeviceCapability] = Field(max_length=50)
    availability: Literal["online", "offline", "degraded", "unknown"]
    observed_at: str | None = Field(default=None, alias="observedAt", max_length=40)


class DeviceCommandProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2_000)
    locale: Literal["de", "en"]
    devices: list[RuntimeDevice] = Field(max_length=250)
    prior_messages: list[ChatMessage] = Field(
        default_factory=list,
        alias="priorMessages",
        max_length=6,
    )


class DeviceTargetSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_name: str | None = Field(default=None, alias="roomName", min_length=1, max_length=120)
    provider: Literal["nanoleaf"]
    device_id: str | None = Field(default=None, alias="deviceId", min_length=1, max_length=128)

    @model_validator(mode="after")
    def exactly_one_target(self) -> "DeviceTargetSelector":
        if (self.room_name is None) == (self.device_id is None):
            raise ValueError("exactly one device target is required")
        return self


class DeviceCommandArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on: bool | None = None
    brightness: int | None = Field(default=None, ge=0, le=100)


class DeviceCommandProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Literal["power.set", "light.setBrightness"]
    selector: DeviceTargetSelector
    arguments: DeviceCommandArguments


class DeviceCommandProposalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: DeviceCommandProposal | None


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
