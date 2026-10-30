"""Official cloud HTTP APIs. All transports are injectable for simulated tests."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing
from uuid import uuid4

import httpx
from pydantic import JsonValue, ValidationError

from kyrion_ai.contracts import ChatEvent, ChatRequest
from kyrion_ai.model_contracts import ModelProfile, TokenUsage, ToolCall
from kyrion_ai.providers.http_stream import (
  ProviderFailure,
  count,
  encoded,
  json_object,
  object_value,
  objects,
  stream_json,
  text,
)
from kyrion_ai.tools import validate_call


class CloudProvider:
  provider_id: str
  url: str

  def __init__(self, key: str, transport: httpx.AsyncBaseTransport | None = None):
    self.key = key
    self.transport = transport

  def request(
    self, request: ChatRequest, profile: ModelProfile
  ) -> tuple[str, dict[str, str], dict[str, JsonValue]]:
    raise NotImplementedError

  async def decode(
    self, records: AsyncIterator[dict[str, JsonValue]], request: ChatRequest, message_id: str
  ) -> AsyncIterator[ChatEvent]:
    raise NotImplementedError
    yield  # pragma: no cover

  async def stream_chat(
    self, request: ChatRequest, profile: ModelProfile
  ) -> AsyncIterator[ChatEvent]:
    message_id = str(uuid4())
    try:
      async with asyncio.timeout(profile.timeouts.total_seconds):
        url, headers, payload = self.request(request, profile)
        records = stream_json(url, headers, payload, profile, self.transport)
        yield ChatEvent(type="message.started", message_id=message_id)
        async with (
          aclosing(records),
          aclosing(self.decode(records, request, message_id)) as decoded,
        ):
          async for event in decoded:
            yield event
    except (TimeoutError, httpx.TimeoutException):
      yield ChatEvent(type="error", code="REQUEST_TIMEOUT")
    except ProviderFailure as error:
      yield ChatEvent(type="error", code=error.code)
    except httpx.ConnectError:
      yield ChatEvent(type="error", code="MODEL_UNAVAILABLE")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError):
      yield ChatEvent(type="error", code="STREAM_FAILED")
    # CancelledError intentionally propagates and closes the HTTP context.


def finish(reason: str, message_id: str) -> ChatEvent:
  if reason in {"length", "max_tokens", "MAX_TOKENS", "max_output_tokens"}:
    return ChatEvent(type="error", code="OUTPUT_LIMIT_REACHED")
  if reason in {
    "refusal",
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "content_filter",
  }:
    return ChatEvent(type="error", code="PROVIDER_REFUSED")
  return ChatEvent(type="message.completed", message_id=message_id, finish_reason=reason)


class OpenAIProvider(CloudProvider):
  provider_id = "openai"

  def request(self, request: ChatRequest, profile: ModelProfile):
    inputs: list[JsonValue] = []
    seen_reasoning: set[str] = set()
    for message in request.messages:
      if message.role == "system":
        continue
      if message.content:
        inputs.append({"role": message.role, "content": message.content})
      for call in message.tool_calls:
        for reasoning in call.provider_state.get("openaiReasoning", []):
          identity = encoded(reasoning)
          if identity not in seen_reasoning:
            inputs.append(reasoning)
            seen_reasoning.add(identity)
        inputs.append(
          {
            "type": "function_call",
            "call_id": call.id,
            "name": call.name,
            "arguments": encoded(call.arguments),
          }
        )
      if result := message.tool_result:
        inputs.append(
          {
            "type": "function_call_output",
            "call_id": result.call_id,
            "output": encoded(result.result),
          }
        )
    payload: dict[str, JsonValue] = {
      "model": profile.model_id,
      "input": inputs,
      "stream": True,
      "store": False,
      "max_output_tokens": profile.max_output_tokens,
      "instructions": "\n\n".join(m.content for m in request.messages if m.role == "system"),
    }
    if request.tools:
      payload["tools"] = [
        {
          "type": "function",
          "name": tool.name,
          "description": tool.description,
          "parameters": tool.parameters,
          "strict": False,
        }
        for tool in request.tools
      ]
      payload["include"] = ["reasoning.encrypted_content"]
    return (
      "https://api.openai.com/v1/responses",
      {"Authorization": f"Bearer {self.key}"},
      payload,
    )

  async def decode(self, records, request, message_id):
    reasoning: list[JsonValue] = []
    calls: set[str] = set()
    async for record in records:
      kind = record.get("type")
      if kind == "response.output_text.delta":
        yield ChatEvent(
          type="message.delta", message_id=message_id, delta=text(record.get("delta"))
        )
      elif kind == "response.refusal.delta":
        raise ProviderFailure("PROVIDER_REFUSED")
      elif kind == "response.output_item.done":
        item = object_value(record.get("item"))
        if item.get("type") == "reasoning":
          reasoning.append(item)
        elif item.get("type") == "function_call":
          call = validate_call(
            ToolCall(
              id=text(item.get("call_id")),
              name=text(item.get("name")),
              arguments=json_object(text(item.get("arguments"))),
              providerState={"openaiReasoning": reasoning},
            ),
            request.tools,
          )
          if call.id in calls:
            raise ProviderFailure("TOOL_CALL_INVALID")
          calls.add(call.id)
          yield ChatEvent(type="tool.call", tool_call=call)
      elif kind in {"response.completed", "response.incomplete"}:
        response = object_value(record.get("response"))
        usage = object_value(response.get("usage") or {})
        yield ChatEvent(
          type="usage",
          usage=TokenUsage(
            inputTokens=count(usage.get("input_tokens")),
            outputTokens=count(usage.get("output_tokens")),
            totalTokens=count(usage.get("total_tokens")),
          ),
        )
        reason = "tool_calls" if calls else "stop"
        if kind == "response.incomplete":
          reason = text(object_value(response.get("incomplete_details")).get("reason"))
        yield finish(reason, message_id)
        return
      elif kind in {"error", "response.failed"}:
        raise ProviderFailure("MODEL_UNAVAILABLE")
    raise ProviderFailure("STREAM_FAILED")


class AnthropicProvider(CloudProvider):
  provider_id = "anthropic"

  def request(self, request: ChatRequest, profile: ModelProfile):
    messages: list[JsonValue] = []
    for message in request.messages:
      if message.role == "system":
        continue
      blocks: list[JsonValue] = []
      if message.content:
        blocks.append({"type": "text", "text": message.content})
      for call in message.tool_calls:
        blocks.append(
          {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
        )
      if result := message.tool_result:
        blocks.append(
          {
            "type": "tool_result",
            "tool_use_id": result.call_id,
            "content": encoded(result.result),
            "is_error": result.is_error,
          }
        )
      messages.append(
        {"role": "user" if message.role == "tool" else message.role, "content": blocks}
      )
    payload: dict[str, JsonValue] = {
      "model": profile.model_id,
      "messages": messages,
      "stream": True,
      "max_tokens": profile.max_output_tokens,
      "system": "\n\n".join(m.content for m in request.messages if m.role == "system"),
    }
    if request.tools:
      payload["tools"] = [
        {
          "name": tool.name,
          "description": tool.description,
          "input_schema": tool.parameters,
        }
        for tool in request.tools
      ]
    return (
      "https://api.anthropic.com/v1/messages",
      {
        "x-api-key": self.key,
        "anthropic-version": "2023-06-01",
      },
      payload,
    )

  async def decode(self, records, request, message_id):
    blocks: dict[int, dict[str, JsonValue]] = {}
    arguments: dict[int, str] = {}
    usage = TokenUsage()
    reason = "stop"
    calls: set[str] = set()
    async for record in records:
      kind = record.get("type")
      index = count(record.get("index"))
      if kind == "message_start":
        initial = object_value(object_value(record.get("message")).get("usage") or {})
        usage.input_tokens = count(initial.get("input_tokens"))
        usage.cached_input_tokens = count(initial.get("cache_read_input_tokens"))
      elif kind == "content_block_start" and index is not None:
        blocks[index] = object_value(record.get("content_block"))
        arguments[index] = ""
      elif kind == "content_block_delta":
        delta = object_value(record.get("delta"))
        if delta.get("type") == "text_delta":
          yield ChatEvent(
            type="message.delta", message_id=message_id, delta=text(delta.get("text"))
          )
        elif delta.get("type") == "input_json_delta" and index in arguments:
          arguments[index] += text(delta.get("partial_json"))
          if len(arguments[index]) > 64_000:
            raise ProviderFailure("TOOL_CALL_INVALID")
      elif kind == "content_block_stop" and index in blocks:
        block = blocks.pop(index)
        if block.get("type") == "tool_use":
          call = validate_call(
            ToolCall(
              id=text(block.get("id")),
              name=text(block.get("name")),
              arguments=json_object(arguments[index])
              if arguments[index]
              else object_value(block.get("input")),
            ),
            request.tools,
          )
          if call.id in calls:
            raise ProviderFailure("TOOL_CALL_INVALID")
          calls.add(call.id)
          yield ChatEvent(type="tool.call", tool_call=call)
      elif kind == "message_delta":
        reason = text(object_value(record.get("delta")).get("stop_reason"))
        usage.output_tokens = count(
          object_value(record.get("usage") or {}).get("output_tokens")
        )
      elif kind == "message_stop":
        if blocks:
          raise ProviderFailure("STREAM_FAILED")
        if usage.input_tokens is not None and usage.output_tokens is not None:
          usage.total_tokens = usage.input_tokens + usage.output_tokens
        yield ChatEvent(type="usage", usage=usage)
        yield finish(reason, message_id)
        return
      elif kind == "error":
        code = object_value(record.get("error")).get("type")
        raise ProviderFailure(
          "RATE_LIMITED" if code == "rate_limit_error" else "MODEL_UNAVAILABLE"
        )
    raise ProviderFailure("STREAM_FAILED")


class GeminiProvider(CloudProvider):
  provider_id = "gemini"

  def request(self, request: ChatRequest, profile: ModelProfile):
    import re

    model = profile.model_id.removeprefix("models/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", model):
      raise ProviderFailure("INVALID_REQUEST")
    contents: list[JsonValue] = []
    for message in request.messages:
      if message.role == "system":
        continue
      parts: list[JsonValue] = [{"text": message.content}] if message.content else []
      for call in message.tool_calls:
        function: dict[str, JsonValue] = {"name": call.name, "args": call.arguments}
        if call.provider_state.get("geminiCallId"):
          function["id"] = call.provider_state["geminiCallId"]
        part: dict[str, JsonValue] = {"functionCall": function}
        if call.provider_state.get("geminiThoughtSignature"):
          part["thoughtSignature"] = call.provider_state["geminiThoughtSignature"]
        parts.append(part)
      if result := message.tool_result:
        parts.append(
          {
            "functionResponse": {
              "name": result.name,
              "response": {"error" if result.is_error else "result": result.result},
            }
          }
        )
      contents.append(
        {"role": "model" if message.role == "assistant" else "user", "parts": parts}
      )
    payload: dict[str, JsonValue] = {
      "contents": contents,
      "systemInstruction": {
        "parts": [
          {"text": "\n\n".join(m.content for m in request.messages if m.role == "system")}
        ]
      },
      "generationConfig": {"maxOutputTokens": profile.max_output_tokens, "candidateCount": 1},
    }
    if request.tools:
      payload["tools"] = [
        {
          "functionDeclarations": [
            {
              "name": tool.name,
              "description": tool.description,
              "parametersJsonSchema": tool.parameters,
            }
            for tool in request.tools
          ]
        }
      ]
    return (
      f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse",
      {
        "x-goog-api-key": self.key,
      },
      payload,
    )

  async def decode(self, records, request, message_id):
    reason = None
    calls: set[str] = set()
    async for record in records:
      if record.get("error"):
        raise ProviderFailure("MODEL_UNAVAILABLE")
      if object_value(record.get("promptFeedback") or {}).get("blockReason"):
        raise ProviderFailure("PROVIDER_REFUSED")
      for candidate in objects(record.get("candidates") or []):
        for part in objects(
          object_value(candidate.get("content") or {}).get("parts") or []
        ):
          if "text" in part and not part.get("thought"):
            yield ChatEvent(
              type="message.delta", message_id=message_id, delta=text(part["text"])
            )
          if "functionCall" in part:
            function = object_value(part["functionCall"])
            native_id = function.get("id")
            state = (
              {"geminiThoughtSignature": part["thoughtSignature"]}
              if "thoughtSignature" in part
              else {}
            )
            if native_id:
              state["geminiCallId"] = native_id
            call = validate_call(
              ToolCall(
                id=text(native_id) if native_id else str(uuid4()),
                name=text(function.get("name")),
                arguments=object_value(function.get("args") or {}),
                providerState=state,
              ),
              request.tools,
            )
            if call.id in calls:
              raise ProviderFailure("TOOL_CALL_INVALID")
            calls.add(call.id)
            yield ChatEvent(type="tool.call", tool_call=call)
        if candidate.get("finishReason"):
          reason = text(candidate["finishReason"])
      if record.get("usageMetadata"):
        usage = object_value(record["usageMetadata"])
        yield ChatEvent(
          type="usage",
          usage=TokenUsage(
            inputTokens=count(usage.get("promptTokenCount")),
            outputTokens=count(usage.get("candidatesTokenCount")),
            totalTokens=count(usage.get("totalTokenCount")),
            cachedInputTokens=count(usage.get("cachedContentTokenCount")),
          ),
        )
    if reason is None:
      raise ProviderFailure("STREAM_FAILED")
    if reason not in {"STOP", "MAX_TOKENS"}:
      raise ProviderFailure("PROVIDER_REFUSED")
    yield finish("tool_calls" if calls and reason == "STOP" else reason, message_id)
