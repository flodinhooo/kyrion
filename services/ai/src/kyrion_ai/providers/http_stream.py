"""Bounded HTTP/SSE transport shared by cloud adapters; never logs upstream bodies."""

import json
from collections.abc import AsyncIterator

import httpx
from pydantic import JsonValue, TypeAdapter

from kyrion_ai.contracts import ChatErrorCode
from kyrion_ai.model_contracts import ModelProfile

JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class ProviderFailure(Exception):
  def __init__(self, code: ChatErrorCode):
    self.code = code
    super().__init__(code)


def object_value(value: JsonValue) -> dict[str, JsonValue]:
  if not isinstance(value, dict):
    raise ProviderFailure("STREAM_FAILED")
  return value


def objects(value: JsonValue) -> list[dict[str, JsonValue]]:
  if not isinstance(value, list):
    raise ProviderFailure("STREAM_FAILED")
  return [object_value(item) for item in value]


def text(value: JsonValue) -> str:
  if not isinstance(value, str):
    raise ProviderFailure("STREAM_FAILED")
  return value


def count(value: JsonValue) -> int | None:
  return value if type(value) is int and value >= 0 else None


def json_object(raw: str) -> dict[str, JsonValue]:
  if len(raw) > 1_000_000:
    raise ProviderFailure("STREAM_FAILED")
  try:
    return JSON_OBJECT.validate_json(raw)
  except ValueError as error:
    raise ProviderFailure("STREAM_FAILED") from error


def status_failure(status: int) -> ProviderFailure:
  code: ChatErrorCode = (
    "PROVIDER_AUTH_FAILED"
    if status in {401, 403}
    else "RATE_LIMITED"
    if status == 429
    else "REQUEST_TIMEOUT"
    if status in {408, 504}
    else "CAPABILITY_UNSUPPORTED"
    if status == 400
    else "MODEL_UNAVAILABLE"
  )
  return ProviderFailure(code)


async def stream_json(
  url: str,
  headers: dict[str, str],
  payload: dict[str, JsonValue],
  profile: ModelProfile,
  transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[dict[str, JsonValue]]:
  timeout = httpx.Timeout(
    connect=profile.timeouts.connect_seconds,
    read=profile.timeouts.read_seconds,
    write=30,
    pool=5,
  )
  async with (
    httpx.AsyncClient(
      timeout=timeout, transport=transport, follow_redirects=False, trust_env=False
    ) as client,
    client.stream("POST", url, headers=headers, json=payload) as response,
  ):
    if not response.is_success:
      raise status_failure(response.status_code)
    data: list[str] = []
    size = 0
    async for line in response.aiter_lines():
      if line.startswith("data:"):
        part = line[5:].lstrip()
        size += len(part)
        if size > 1_000_000:
          raise ProviderFailure("STREAM_FAILED")
        data.append(part)
      elif not line and data:
        raw = "\n".join(data)
        data, size = [], 0
        if raw != "[DONE]":
          yield json_object(raw)
    if data:
      raw = "\n".join(data)
      if raw != "[DONE]":
        yield json_object(raw)


def encoded(value: JsonValue) -> str:
  return json.dumps(value, ensure_ascii=False, allow_nan=False)
