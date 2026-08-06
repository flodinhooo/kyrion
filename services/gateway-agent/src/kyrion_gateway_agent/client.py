from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from kyrion_gateway_agent import __version__
from kyrion_gateway_agent.config import AgentConfig


class CoreRequestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EnrollmentResult:
    node_id: str
    gateway_token: str


def enroll(core_url: str, enrollment_token: str, identity: dict[str, str]) -> EnrollmentResult:
    value = _request(
        f"{core_url.rstrip('/')}/v1/gateway-agent/enroll",
        "POST",
        {
            "enrollmentToken": enrollment_token,
            "agentVersion": __version__,
            **identity,
        },
    )
    node_id = value.get("nodeId") if isinstance(value, dict) else None
    gateway_token = value.get("gatewayToken") if isinstance(value, dict) else None
    if not isinstance(node_id, str) or not isinstance(gateway_token, str):
        raise CoreRequestError("Core returned an invalid enrollment response")
    return EnrollmentResult(node_id, gateway_token)


def heartbeat(config: AgentConfig, health: dict[str, Any]) -> None:
    _request(
        f"{config.core_url}/v1/gateway-agent/heartbeat",
        "PUT",
        {"health": health},
        {
            "Authorization": f"Bearer {config.gateway_token}",
            "X-Kyrion-Node-Id": config.node_id,
        },
        expect_json=False,
    )


def _request(
    url: str,
    method: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    *,
    expect_json: bool = True,
) -> Any:
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=10) as response:
            if not expect_json:
                return None
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise CoreRequestError(f"Core rejected the request with HTTP {error.code}") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CoreRequestError("Core is unavailable or returned invalid data") from error
