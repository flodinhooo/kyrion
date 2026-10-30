"""SIMULATED HTTP acceptance for the existing AI API contract and new profile gates."""

import asyncio
import json
from dataclasses import replace
from importlib import import_module
from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatMessage, ChatRequest
from kyrion_ai.model_contracts import ToolCall, ToolResult
from kyrion_ai.models import ModelRegistry


def test_simulated_api_routes_switch_to_configured_cloud_and_reject_memory(tmp_path, monkeypatch):
  app_module = import_module("kyrion_ai.app")
  config = tmp_path / "profiles.json"
  config.write_text(
    json.dumps(
      {
        "profiles": [
          {
            "id": "gpt",
            "provider": "openai",
            "modelId": "operator-gpt",
            "label": "GPT",
            "capabilities": ["chat", "streaming"],
          }
        ]
      }
    )
  )
  seen = []

  def handler(incoming):
    seen.append(json.loads(incoming.content))
    return httpx.Response(
      200,
      text='data: {"type":"response.output_text.delta","delta":"OK"}\n\n'
           'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":1,"total_tokens":5}}}\n\n',
    )

  settings = Settings(
    "http://localhost:11434",
    "local",
    ("local",),
    1,
    model_profiles_file=config,
    model_cloud_enabled=True,
    openai_api_key="synthetic",
  )
  models = ModelRegistry(settings, transport=httpx.MockTransport(handler))
  models.ollama.list_models = AsyncMock(side_effect=httpx.ConnectError("local offline"))
  monkeypatch.setattr(app_module, "models", models)
  with TestClient(app_module.app) as client:
    catalog = client.get("/v1/models").json()
    assert len(catalog["providers"]) == 4
    assert next(m for m in catalog["models"] if m["id"] == "gpt")["available"]
    payload = {
      "locale": "en",
      "modelId": "gpt",
      "cloudConsent": True,
      "messages": [{"role": "user", "content": "Synthetic current prompt"}],
    }
    response = client.post("/v1/chat/stream", json=payload)
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["provider"] == "openai" and events[-1]["type"] == "message.completed"
    assert seen[0]["model"] == "operator-gpt"
    assert "instructions" in seen[0] and "Velora" in seen[0]["instructions"]
    assert (
      client.post("/v1/chat/stream", json={**payload, "cloudConsent": False}).json()["code"]
      == "CLOUD_NOT_ALLOWED"
    )
    rejected = client.post(
      "/v1/chat/stream",
      json={
        **payload,
        "memoryContext": [
          {
            "id": "m",
            "category": "other",
            "content": "PRIVATE",
            "sensitivity": "sensitive",
          }
        ],
      },
    )
    assert rejected.status_code == 400 and rejected.json()["code"] == "CONTEXT_NOT_ALLOWED"
    assert len(seen) == 1
    assert (
      client.post("/v1/models/benchmark", json={"modelId": "gpt", "locale": "en"}).status_code
      == 400
    )
    assert len(seen) == 1  # Cloud benchmarks never make paid calls.


def test_simulated_ollama_retains_wire_contract_and_adds_usage(monkeypatch):
  actual_client = httpx.AsyncClient
  seen = []

  def handler(incoming):
    seen.append(json.loads(incoming.content))
    return httpx.Response(
      200,
      text='{"message":{"content":"OK"},"done":false}\n'
           '{"message":{"content":""},"done":true,"prompt_eval_count":4,"eval_count":1}\n',
    )

  monkeypatch.setattr(
    httpx,
    "AsyncClient",
    lambda **options: actual_client(**options, transport=httpx.MockTransport(handler)),
  )
  settings = Settings("http://localhost:11434", "local", ("local",), 1)
  models = ModelRegistry(settings)

  async def run():
    return [
      event
      async for event in models.stream_chat(
        ChatRequest(locale="en", messages=[ChatMessage(role="user", content="Test")])
      )
    ]

  events = asyncio.run(run())
  assert events[-1].type == "message.completed"
  assert next(e.usage for e in events if e.type == "usage").input_tokens == 4
  assert seen[0]["messages"][-1] == {"role": "user", "content": "Test"}
  assert seen[0]["model"] == "local" and seen[0]["stream"] is True


def test_duplicate_tool_results_and_mismatched_names_are_rejected_before_provider_access():
  import pytest
  from test_multi_provider import TOOL

  from kyrion_ai.providers.http_stream import ProviderFailure

  models = ModelRegistry(Settings("http://localhost:11434", "local", ("local",), 1))
  models.profiles["local"].capabilities.append("tools")
  call = ChatMessage(
    role="assistant", toolCalls=[ToolCall(id="c1", name=TOOL.name, arguments={"on": True})]
  )
  result = ChatMessage(
    role="tool", toolResult=ToolResult(callId="c1", name=TOOL.name, result={"status": "ok"})
  )
  for messages in [[call, result, result], [result], [call, call]]:
    with pytest.raises(ProviderFailure, match="TOOL_CALL_INVALID"):
      models.resolve(ChatRequest(locale="en", messages=messages, tools=[TOOL]))


def test_credentials_are_not_in_settings_representation():
  settings = replace(
    Settings("http://local", "local", ("local",), 1),
    openai_api_key="PRIVATE_OAI",
    anthropic_api_key="PRIVATE_ANTHROPIC",
    gemini_api_key="PRIVATE_GEMINI",
  )
  assert "PRIVATE" not in repr(settings)
