"""SIMULATED cloud APIs: no credentials, billable calls or device execution."""

import asyncio
import json
from dataclasses import replace
from unittest.mock import AsyncMock

import httpx
import pytest

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatMessage, ChatRequest
from kyrion_ai.model_contracts import (
  ModelProfile,
  ModelTimeouts,
  ToolCall,
  ToolDefinition,
  ToolResult,
)
from kyrion_ai.models import ModelRegistry
from kyrion_ai.providers.cloud import AnthropicProvider, GeminiProvider, OpenAIProvider
from kyrion_ai.providers.http_stream import ProviderFailure
from kyrion_ai.tools import validate_call, validate_schema

ADAPTERS = {"openai": OpenAIProvider, "anthropic": AnthropicProvider, "gemini": GeminiProvider}
TOOL = ToolDefinition(
  name="light_power",
  parameters={
    "type": "object",
    "properties": {"on": {"type": "boolean"}},
    "required": ["on"],
    "additionalProperties": False,
  },
)


def profile(provider, **values):
  return ModelProfile(
    id=f"{provider}:test",
    provider=provider,
    modelId="models/operator-model" if provider == "gemini" else "operator-model",
    label="Configured model",
    capabilities=["chat", "streaming", "tools"],
    **values,
  )


def request(**values):
  return ChatRequest(
    locale="en", messages=[ChatMessage(role="user", content="Synthetic test")], **values
  )


def sse(records):
  return "".join(f"data: {json.dumps(record)}\n\n" for record in records)


def completed(provider, tool=False):
  if provider == "openai":
    return (
      [
        {
          "type": "response.output_item.done",
          "item": {
            "type": "function_call",
            "call_id": "call1",
            "name": TOOL.name,
            "arguments": '{"on":true}',
          },
        }
      ]
      if tool
      else [{"type": "response.output_text.delta", "delta": "Hello"}]
    ) + [
      {
        "type": "response.completed",
        "response": {"usage": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6}},
      }
    ]
  if provider == "anthropic":
    return (
      [{"type": "message_start", "message": {"usage": {"input_tokens": 4}}}]
      + (
        [
          {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
              "type": "tool_use",
              "id": "call1",
              "name": TOOL.name,
              "input": {},
            },
          },
          {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"on":'},
          },
          {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": "true}"},
          },
          {"type": "content_block_stop", "index": 0},
        ]
        if tool
        else [
          {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hello"},
          }
        ]
      )
      + [
        {
          "type": "message_delta",
          "delta": {"stop_reason": "tool_use" if tool else "end_turn"},
          "usage": {"output_tokens": 2},
        },
        {"type": "message_stop"},
      ]
    )
  return [
    {
      "candidates": [
        {
          "content": {
            "parts": [
              {
                "functionCall": {
                  "id": "call1",
                  "name": TOOL.name,
                  "args": {"on": True},
                },
                "thoughtSignature": "opaque-signature",
              }
            ]
            if tool
            else [{"text": "Hello"}]
          },
          "finishReason": "STOP",
        }
      ],
      "usageMetadata": {
        "promptTokenCount": 4,
        "candidatesTokenCount": 2,
        "totalTokenCount": 6,
      },
    }
  ]


def collect(adapter, message, selected):
  async def run():
    return [event async for event in adapter.stream_chat(message, selected)]

  return asyncio.run(run())


@pytest.mark.parametrize("provider", ADAPTERS)
@pytest.mark.parametrize("tool", [False, True])
def test_simulated_stream_normalizes_text_tools_usage_and_official_wire_format(provider, tool):
  captured = []

  def handler(incoming):
    captured.append(incoming)
    return httpx.Response(200, text=sse(completed(provider, tool)))

  adapter = ADAPTERS[provider]("synthetic-test-key", httpx.MockTransport(handler))
  events = collect(adapter, request(tools=[TOOL] if tool else []), profile(provider))
  assert events[-1].type == "message.completed"
  assert next(event.usage for event in events if event.type == "usage").total_tokens == 6
  if tool:
    call = next(event.tool_call for event in events if event.type == "tool.call")
    assert call.id == "call1" and call.name == TOOL.name and call.arguments == {"on": True}
    if provider == "gemini":
      assert call.provider_state["geminiThoughtSignature"] == "opaque-signature"
  else:
    assert "".join(event.delta or "" for event in events) == "Hello"
  wire = json.loads(captured[0].content)
  assert "synthetic-test-key" not in captured[0].url.query.decode()
  if provider == "openai":
    assert captured[0].url.path == "/v1/responses" and wire["store"] is False
  elif provider == "anthropic":
    assert captured[0].url.path == "/v1/messages" and wire["max_tokens"] == 1024
  else:
    assert captured[0].url.path.endswith("/models/operator-model:streamGenerateContent")


@pytest.mark.parametrize("provider", ADAPTERS)
@pytest.mark.parametrize(
  ("status", "code"),
  [
    (401, "PROVIDER_AUTH_FAILED"),
    (403, "PROVIDER_AUTH_FAILED"),
    (429, "RATE_LIMITED"),
    (500, "MODEL_UNAVAILABLE"),
    (400, "CAPABILITY_UNSUPPORTED"),
  ],
)
def test_simulated_http_errors_never_expose_provider_bodies_or_credentials(provider, status, code):
  adapter = ADAPTERS[provider](
    "secret",
    httpx.MockTransport(lambda _: httpx.Response(status, text="private provider body secret")),
  )
  events = collect(adapter, request(), profile(provider))
  assert events[-1].code == code
  assert "secret" not in "".join(event.to_ndjson().decode() for event in events)


@pytest.mark.parametrize("provider", ADAPTERS)
def test_simulated_missing_terminal_event_is_failure(provider):
  adapter = ADAPTERS[provider](
    "test", httpx.MockTransport(lambda _: httpx.Response(200, text="data: {}\n\n"))
  )
  assert collect(adapter, request(), profile(provider))[-1].code == "STREAM_FAILED"


@pytest.mark.parametrize("provider", ADAPTERS)
def test_simulated_read_timeout(provider):
  def handler(incoming):
    raise httpx.ReadTimeout("private timeout info", request=incoming)

  adapter = ADAPTERS[provider]("test", httpx.MockTransport(handler))
  assert collect(adapter, request(), profile(provider))[-1].code == "REQUEST_TIMEOUT"


def test_simulated_total_deadline_and_cancellation_close_upstream():
  class SlowStream(httpx.AsyncByteStream):
    closed = False

    async def __aiter__(self):
      yield b'data: {"type":"response.output_text.delta","delta":"Hello"}\n\n'
      await asyncio.sleep(60)

    async def aclose(self):
      self.closed = True

  async def run(cancel):
    source = SlowStream()
    adapter = OpenAIProvider(
      "test", httpx.MockTransport(lambda _: httpx.Response(200, stream=source))
    )
    stream = adapter.stream_chat(
      request(), profile("openai", timeouts=ModelTimeouts(totalSeconds=0.03))
    )
    assert (await anext(stream)).type == "message.started"
    assert (await anext(stream)).delta == "Hello"
    if cancel:
      task = asyncio.create_task(anext(stream))
      await asyncio.sleep(0)
      task.cancel()
      with pytest.raises(asyncio.CancelledError):
        await task
    else:
      assert (await anext(stream)).code == "REQUEST_TIMEOUT"
    await stream.aclose()
    assert source.closed

  asyncio.run(run(False))
  asyncio.run(run(True))


def registry(tmp_path, **options):
  file = tmp_path / "profiles.json"
  file.write_text(
    json.dumps({"profiles": [profile(name).model_dump(by_alias=True) for name in ADAPTERS]})
  )
  settings = Settings("http://127.0.0.1:11434", "local", ("local",), 1, model_profiles_file=file)
  return ModelRegistry(replace(settings, **options))


def test_local_default_and_legacy_voice_share_configuration(tmp_path):
  models = registry(tmp_path)
  assert models.resolve(request()).id == "local"
  assert models.resolve(request(interactionMode="voice", modelId="gemma3:1b")).id == "local"
  assert not any(status.enabled for status in models.provider_status() if not status.local)


@pytest.mark.parametrize("provider", ADAPTERS)
def test_cloud_requires_server_enablement_credentials_and_per_request_consent(tmp_path, provider):
  models = registry(tmp_path)
  message = request(modelId=f"{provider}:test", cloudConsent=True)
  with pytest.raises(ProviderFailure, match="CLOUD_NOT_ALLOWED"):
    models.resolve(message)
  models = registry(tmp_path, model_cloud_enabled=True)
  with pytest.raises(ProviderFailure, match="PROVIDER_NOT_CONFIGURED"):
    models.resolve(message)
  key_field = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "gemini": "gemini_api_key",
  }[provider]
  models = registry(tmp_path, model_cloud_enabled=True, **{key_field: "synthetic"})
  assert models.resolve(message).provider == provider
  with pytest.raises(ProviderFailure, match="CLOUD_NOT_ALLOWED"):
    models.resolve(message.model_copy(update={"cloud_consent": False}))
  for update in [
    {"messages": [*message.messages, ChatMessage(role="assistant", content="private history")]},
    {"memory_context": [{"content": "private"}]},
  ]:
    with pytest.raises(ProviderFailure, match="CONTEXT_NOT_ALLOWED"):
      models.resolve(message.model_copy(update=update))


def test_catalog_remains_usable_with_ollama_offline_and_never_calls_cloud(tmp_path):
  models = registry(tmp_path)
  models.ollama.list_models = AsyncMock(side_effect=httpx.ConnectError("offline"))
  catalog = asyncio.run(models.catalog())
  assert catalog.default_model_id == "local"
  assert {p.id for p in catalog.providers} == {"ollama", *ADAPTERS}
  assert all(not model.available for model in catalog.models)
  assert all("key" not in p.model_dump() for p in catalog.providers)


def test_unknown_capabilities_disabled_models_and_schema_constraints_fail_closed(tmp_path):
  models = registry(tmp_path)
  models.profiles["local"] = models.profiles["local"].model_copy(update={"capabilities": []})
  with pytest.raises(ProviderFailure, match="CAPABILITY_UNSUPPORTED"):
    models.resolve(request())
  models.profiles["local"].enabled = False
  with pytest.raises(ProviderFailure, match="MODEL_DISABLED"):
    models.resolve(request())
  for schema in [
    {"type": "object", "$ref": "https://untrusted"},
    {"type": []},
    {"type": "integer", "minimum": "bad"},
  ]:
    with pytest.raises(ProviderFailure):
      validate_schema(schema)
  with pytest.raises(ProviderFailure):
    validate_call(ToolCall(id="id", name=TOOL.name, arguments={"on": "true"}), [TOOL])
  with pytest.raises(ProviderFailure):
    validate_call(ToolCall(id="id", name="unlisted", arguments={"on": True}), [TOOL])


@pytest.mark.parametrize("provider", ADAPTERS)
def test_tool_results_are_serialized_without_execution_and_gemini_signature_is_retained(provider):
  call = ToolCall(
    id="call1",
    name=TOOL.name,
    arguments={"on": True},
    providerState={"geminiThoughtSignature": "opaque", "geminiCallId": "call1"}
    if provider == "gemini"
    else {},
  )
  message = request(tools=[TOOL]).model_copy(
    update={
      "messages": [
        ChatMessage(role="user", content="Test"),
        ChatMessage(role="assistant", toolCalls=[call]),
        ChatMessage(
          role="tool",
          toolResult=ToolResult(
            callId="call1", name=TOOL.name, result={"status": "confirmed"}
          ),
        ),
      ]
    }
  )
  _, _, wire = ADAPTERS[provider]("test").request(message, profile(provider))
  assert "confirmed" in json.dumps(wire)
  if provider == "gemini":
    assert wire["contents"][1]["parts"][0]["thoughtSignature"] == "opaque"
