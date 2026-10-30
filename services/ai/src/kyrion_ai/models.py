"""Trusted model profiles, privacy gates and routing. No automatic fallback."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing

import httpx

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatEvent, ChatRequest, ModelCatalog, ModelInfo
from kyrion_ai.model_contracts import ModelProfile, ProfileConfiguration, ProviderStatus
from kyrion_ai.prompts import prepare_chat_request
from kyrion_ai.providers.base import LanguageModelProvider
from kyrion_ai.providers.cloud import AnthropicProvider, GeminiProvider, OpenAIProvider
from kyrion_ai.providers.http_stream import ProviderFailure
from kyrion_ai.providers.ollama import OllamaProvider
from kyrion_ai.tools import validate_call, validate_schema


class ModelRegistry:
  def __init__(
    self,
    settings: Settings,
    ollama: OllamaProvider | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
  ):
    self.settings = settings
    self.ollama = ollama or OllamaProvider(settings)
    self.adapters: dict[str, LanguageModelProvider] = {"ollama": self.ollama}
    self.keys = {
      "openai": settings.openai_api_key,
      "anthropic": settings.anthropic_api_key,
      "gemini": settings.gemini_api_key,
    }
    for name, factory in [
      ("openai", OpenAIProvider),
      ("anthropic", AnthropicProvider),
      ("gemini", GeminiProvider),
    ]:
      if key := self.keys[name]:
        self.adapters[name] = factory(key, transport)
    self.profiles = {
      model: ModelProfile(
        id=model,
        provider="ollama",
        modelId=model,
        label=model,
        capabilities=["chat", "streaming"],
      )
      for model in settings.ollama_allowed_models
    }
    configured = ProfileConfiguration()
    if settings.model_profiles_file:
      try:
        if settings.model_profiles_file.stat().st_size > 256_000:
          raise ValueError()
        configured = ProfileConfiguration.model_validate_json(
          settings.model_profiles_file.read_text(encoding="utf-8")
        )
      except (ValueError, OSError):
        raise ValueError("MODEL_PROFILES_INVALID") from None
    if len({p.id for p in configured.profiles}) != len(configured.profiles):
      raise ValueError("MODEL_PROFILE_DUPLICATE")
    self.profiles.update({p.id: p for p in configured.profiles})
    self.explicit_profiles = {p.id for p in configured.profiles}
    self.default_id = configured.default_profile_id or settings.ollama_model
    self.voice_id = configured.voice_profile_id or self.default_id
    for profile_id in {self.default_id, self.voice_id}:
      profile = self.profiles.get(profile_id)
      if not profile or not profile.enabled or not profile.local:
        raise ValueError("DEFAULT_AND_VOICE_MUST_BE_LOCAL")

  def provider_status(self) -> list[ProviderStatus]:
    return [
      ProviderStatus(
        id=name,
        local=name == "ollama",
        configured=name == "ollama" or bool(self.keys[name]),
        enabled=name == "ollama" or self.settings.model_cloud_enabled,
        code=None
        if name == "ollama" or (self.keys[name] and self.settings.model_cloud_enabled)
        else "PROVIDER_NOT_CONFIGURED"
        if not self.keys[name]
        else "CLOUD_NOT_ALLOWED",
      )
      for name in ["ollama", "openai", "anthropic", "gemini"]
    ]

  def resolve(self, request: ChatRequest) -> ModelProfile:
    # Bridge the legacy Core voice caller without editing its parallel-owned file.
    selected = (
      self.voice_id
      if request.interaction_mode == "voice"
      else request.model_id or self.default_id
    )
    profile = self.profiles.get(selected)
    if profile is None:
      raise ProviderFailure("INVALID_REQUEST")
    if not profile.enabled:
      raise ProviderFailure("MODEL_DISABLED")
    if not profile.local:
      if not self.settings.model_cloud_enabled or not request.cloud_consent:
        raise ProviderFailure("CLOUD_NOT_ALLOWED")
      if not self.keys[profile.provider]:
        raise ProviderFailure("PROVIDER_NOT_CONFIGURED")
      if (
        request.memory_context
        or len(request.messages) != 1
        or request.messages[0].role != "user"
      ):
        raise ProviderFailure("CONTEXT_NOT_ALLOWED")
    needed = {"chat", "streaming"} | ({"tools"} if request.tools else set())
    if not needed.issubset(profile.capabilities):
      raise ProviderFailure("CAPABILITY_UNSUPPORTED")
    if len({tool.name for tool in request.tools}) != len(request.tools):
      raise ProviderFailure("TOOL_CALL_INVALID")
    for tool in request.tools:
      validate_schema(tool.parameters)
    calls = {}
    results = set()
    for message in request.messages:
      for call in message.tool_calls:
        if call.id in calls:
          raise ProviderFailure("TOOL_CALL_INVALID")
        calls[call.id] = validate_call(call, request.tools)
      if result := message.tool_result:
        if (
          result.call_id not in calls
          or result.call_id in results
          or calls[result.call_id].name != result.name
        ):
          raise ProviderFailure("TOOL_CALL_INVALID")
        results.add(result.call_id)
    return profile

  async def catalog(self) -> ModelCatalog:
    try:
      local_ids = tuple(p.model_id for p in self.profiles.values() if p.local)
      installed = {model.id: model for model in (await self.ollama.list_models(local_ids)).models}
      local_ready = True
    except (httpx.HTTPError, ValueError):
      installed, local_ready = {}, False
    status = {provider.id: provider for provider in self.provider_status()}
    models = []
    for profile in self.profiles.values():
      observed = installed.get(profile.model_id) if profile.local else None
      if observed and profile.id not in self.explicit_profiles:
        # Only known Ollama metadata capabilities are promoted; unknown flags stay unsupported.
        detected = [capability for capability in ("tools", "vision", "audio") if capability in observed.capabilities]
        profile.capabilities = ["chat", "streaming", *detected]
      available = profile.enabled and (
        bool(observed)
        if profile.local
        else status[profile.provider].configured and status[profile.provider].enabled
      )
      code = (
        None
        if available
        else (
          "MODEL_DISABLED"
          if not profile.enabled
          else "MODEL_UNAVAILABLE"
          if profile.local
          else status[profile.provider].code
        )
      )
      models.append(
        ModelInfo(
          id=profile.id,
          label=profile.label,
          provider=profile.provider,
          model_id=profile.model_id,
          local=profile.local,
          enabled=profile.enabled,
          available=available,
          status_code=code,
          size_bytes=observed.size_bytes if observed else 0,
          parameter_size=observed.parameter_size if observed else "unknown",
          quantization=observed.quantization if observed else "unknown",
          capabilities=profile.capabilities,
          context_length=profile.context_length
                         or (observed.context_length if observed else None),
          max_output_tokens=profile.max_output_tokens,
          timeouts=profile.timeouts,
          input_cost_per_million=profile.input_cost_per_million,
          output_cost_per_million=profile.output_cost_per_million,
          currency=profile.currency,
        )
      )
    providers = self.provider_status()
    if not local_ready:
      providers[0].code = "MODEL_UNAVAILABLE"
    return ModelCatalog(default_model_id=self.default_id, models=models, providers=providers)

  async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
    try:
      profile = self.resolve(request)
      prepared = prepare_chat_request(request)
      if (
        profile.context_length
        and sum(len(m.content) for m in prepared.messages) // 4 + profile.max_output_tokens
        > profile.context_length
      ):
        raise ProviderFailure("CONTEXT_LIMIT_EXCEEDED")
      yield ChatEvent(
        type="model.selected",
        provider=profile.provider,
        model_id=profile.model_id,
        profile_id=profile.id,
      )
      async with asyncio.timeout(profile.timeouts.total_seconds):
        async with aclosing(
          self.adapters[profile.provider].stream_chat(prepared, profile)
        ) as stream:
          async for event in stream:
            yield event
    except ProviderFailure as error:
      yield ChatEvent(type="error", code=error.code)
    except (TimeoutError, httpx.TimeoutException):
      yield ChatEvent(type="error", code="REQUEST_TIMEOUT")
