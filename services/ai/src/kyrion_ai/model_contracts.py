"""Provider-independent, bounded model and tool contracts. No execution authority."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ProviderId = Literal["ollama", "openai", "anthropic", "gemini"]
Capability = Literal["chat", "streaming", "tools", "vision", "audio"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ModelTimeouts(StrictModel):
    connect_seconds: float = Field(default=5, alias="connectSeconds", gt=0, le=60)
    read_seconds: float = Field(default=60, alias="readSeconds", gt=0, le=600)
    total_seconds: float = Field(default=180, alias="totalSeconds", gt=0, le=900)


class ModelProfile(StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:/-]+$")
    provider: ProviderId
    model_id: str = Field(
        alias="modelId", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:/-]+$"
    )
    label: str = Field(min_length=1, max_length=160)
    capabilities: list[Capability] = Field(default_factory=list, max_length=5)
    context_length: int | None = Field(default=None, alias="contextLength", gt=0)
    enabled: bool = True
    timeouts: ModelTimeouts = Field(default_factory=ModelTimeouts)
    max_output_tokens: int = Field(default=1024, alias="maxOutputTokens", ge=1, le=32768)
    input_cost_per_million: float | None = Field(default=None, alias="inputCostPerMillion", ge=0)
    output_cost_per_million: float | None = Field(default=None, alias="outputCostPerMillion", ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @property
    def local(self) -> bool:
        return self.provider == "ollama"


class ProfileConfiguration(StrictModel):
    default_profile_id: str | None = Field(default=None, alias="defaultProfileId")
    voice_profile_id: str | None = Field(default=None, alias="voiceProfileId")
    profiles: list[ModelProfile] = Field(default_factory=list, max_length=100)


class ToolDefinition(StrictModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
    description: str = Field(default="", max_length=2000)
    parameters: dict[str, JsonValue]


class ToolCall(StrictModel):
    id: str = Field(min_length=1, max_length=256)
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
    arguments: dict[str, JsonValue]
    # Opaque state is scoped to the producing provider, never executable authority.
    provider_state: dict[str, JsonValue] = Field(default_factory=dict, alias="providerState")


class ToolResult(StrictModel):
    call_id: str = Field(alias="callId", min_length=1, max_length=256)
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
    result: JsonValue
    is_error: bool = Field(default=False, alias="isError")


class TokenUsage(StrictModel):
    input_tokens: int | None = Field(default=None, alias="inputTokens", ge=0)
    output_tokens: int | None = Field(default=None, alias="outputTokens", ge=0)
    total_tokens: int | None = Field(default=None, alias="totalTokens", ge=0)
    cached_input_tokens: int | None = Field(default=None, alias="cachedInputTokens", ge=0)


class ProviderStatus(StrictModel):
    id: ProviderId
    configured: bool
    enabled: bool
    local: bool
    code: str | None = None
