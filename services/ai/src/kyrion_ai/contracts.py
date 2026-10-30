from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kyrion_ai.model_contracts import (
    ModelTimeouts,
    ProviderStatus,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolResult,
)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system", "tool"]
    content: str = Field(default="", max_length=100_000)
    tool_calls: list[ToolCall] = Field(default_factory=list, alias="toolCalls", max_length=16)
    tool_result: ToolResult | None = Field(default=None, alias="toolResult")

    @model_validator(mode="after")
    def valid_content(self) -> "ChatMessage":
        if self.role == "tool":
            if self.tool_result is None or self.tool_calls or self.content:
                raise ValueError("tool messages require only a tool result")
        elif self.tool_result or (self.tool_calls and self.role != "assistant"):
            raise ValueError("tool calls require assistant role")
        elif not self.content and not self.tool_calls:
            raise ValueError("message content required")
        return self


class MemoryContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    category: Literal["preference", "person", "project", "value", "other"]
    content: str = Field(min_length=1, max_length=1_000)
    sensitivity: Literal["standard", "sensitive"]


class KnowledgeContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(alias="documentId", max_length=36)
    filename: str = Field(max_length=200)
    excerpt: str = Field(min_length=1, max_length=2000)
    page: int | None = Field(default=None, ge=1, le=200)
    start_offset: int = Field(alias="startOffset", ge=0)
    end_offset: int = Field(alias="endOffset", ge=1)
    reference: str = Field(pattern=r"^kd:[0-9a-f-]{36}:[0-9]+:[0-9]+$")


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
    cloud_consent: bool = Field(default=False, alias="cloudConsent", strict=True)
    tools: list[ToolDefinition] = Field(default_factory=list, max_length=16)
    knowledge_context: list[KnowledgeContextItem] = Field(
        default_factory=list,
        alias="knowledgeContext",
        max_length=3,
    )


class RuntimeDeviceCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)


class RuntimeDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=60)
    device_class: Literal["light", "switch", "sensor", "other"] = Field(alias="deviceClass")
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
    room_names: list[str] = Field(default_factory=list, alias="roomNames", max_length=8)
    provider: Literal["nanoleaf", "zigbee", "light"]
    device_id: str | None = Field(default=None, alias="deviceId", min_length=1, max_length=128)

    @model_validator(mode="after")
    def exactly_one_target(self) -> "DeviceTargetSelector":
        target_kinds = sum(
            (self.room_name is not None, bool(self.room_names), self.device_id is not None)
        )
        if target_kinds > 1:
            raise ValueError("exactly one device target is required")
        if len({name.casefold() for name in self.room_names}) != len(self.room_names):
            raise ValueError("room targets must be unique")
        if target_kinds == 0 and self.provider != "light":
            raise ValueError("a global target is only valid for the light category")
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
    provider: str = "ollama"
    model_id: str | None = Field(default=None, serialization_alias="modelId")
    local: bool = True
    enabled: bool = True
    available: bool = True
    status_code: str | None = Field(default=None, serialization_alias="statusCode")
    max_output_tokens: int | None = Field(default=None, serialization_alias="maxOutputTokens")
    timeouts: ModelTimeouts | None = None
    input_cost_per_million: float | None = Field(
        default=None, serialization_alias="inputCostPerMillion"
    )
    output_cost_per_million: float | None = Field(
        default=None, serialization_alias="outputCostPerMillion"
    )
    currency: str | None = None


class ModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_model_id: str = Field(serialization_alias="defaultModelId")
    models: list[ModelInfo]
    providers: list[ProviderStatus] = Field(default_factory=list)
    voice_profile_id: str | None = Field(default=None, serialization_alias="voiceProfileId")


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
    "PROVIDER_NOT_CONFIGURED",
    "CLOUD_NOT_ALLOWED",
    "MODEL_DISABLED",
    "CAPABILITY_UNSUPPORTED",
    "PROVIDER_AUTH_FAILED",
    "RATE_LIMITED",
    "REQUEST_TIMEOUT",
    "CONTEXT_NOT_ALLOWED",
    "CONTEXT_LIMIT_EXCEEDED",
    "TOOL_CALL_INVALID",
    "PROVIDER_REFUSED",
    "OUTPUT_LIMIT_REACHED",
]


class ChatEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "message.started",
        "message.delta",
        "message.completed",
        "error",
        "tool.call",
        "tool.result",
        "usage",
        "model.selected",
    ]
    message_id: str | None = Field(default=None, serialization_alias="messageId")
    delta: str | None = None
    code: ChatErrorCode | None = None
    provider: str | None = None
    model_id: str | None = Field(default=None, serialization_alias="modelId")
    profile_id: str | None = Field(default=None, serialization_alias="profileId")
    tool_call: ToolCall | None = Field(default=None, serialization_alias="toolCall")
    tool_result: ToolResult | None = Field(default=None, serialization_alias="toolResult")
    usage: TokenUsage | None = None
    finish_reason: str | None = Field(default=None, serialization_alias="finishReason")

    def to_ndjson(self) -> bytes:
        return self.model_dump_json(by_alias=True, exclude_none=True).encode() + b"\n"


class VoiceResponseSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["entityName"]
    value: str = Field(min_length=1, max_length=120)


class VoiceResponsePlanBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_type: str = Field(alias="responseType", min_length=1, max_length=80)
    locale: Literal["de", "en"]
    voice_profile_id: str = Field(alias="voiceProfileId", pattern="^[a-z0-9_-]{1,40}$")
    voice_profile_revision: str = Field(
        alias="voiceProfileRevision", pattern="^[a-zA-Z0-9._:-]{1,128}$"
    )
    catalog_revision: str = Field(alias="catalogRevision", pattern="^[a-zA-Z0-9._-]{1,80}$")
    rendered_text: str = Field(alias="renderedText", min_length=1, max_length=4_000)


class FixedVoiceResponsePlan(VoiceResponsePlanBase):
    kind: Literal["fixed"]
    response_key: str = Field(alias="responseKey", min_length=1, max_length=80)
    variant_id: str = Field(alias="variantId", pattern="^[a-z0-9_-]{1,40}$")


class TemplateVoiceResponsePlan(VoiceResponsePlanBase):
    kind: Literal["template"]
    template_key: str = Field(alias="templateKey", min_length=1, max_length=80)
    slots: dict[str, VoiceResponseSlot] = Field(max_length=12)
    cache_scope: str = Field(alias="cacheScope", pattern="^[a-f0-9]{64}$")


class DynamicVoiceResponsePlan(VoiceResponsePlanBase):
    kind: Literal["dynamic"]


VoiceResponsePlan = Annotated[
    FixedVoiceResponsePlan | TemplateVoiceResponsePlan | DynamicVoiceResponsePlan,
    Field(discriminator="kind"),
]
