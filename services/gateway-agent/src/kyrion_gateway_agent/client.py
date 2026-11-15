from __future__ import annotations

import hashlib
import hmac
import json
import ssl
import time
import uuid
from dataclasses import dataclass
from email.message import Message
from functools import lru_cache
from http.client import HTTPResponse
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from kyrion_gateway_agent import __version__
from kyrion_gateway_agent.config import AgentConfig
from kyrion_gateway_agent.lan_transport import LocalHTTPSHandler


class CoreRequestError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def permission_time() -> float:
    if hasattr(time, "CLOCK_BOOTTIME"):
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    return time.monotonic()


@dataclass(frozen=True, slots=True)
class TaskLease:
    allowed_tasks: frozenset[str]
    expires_at: float

    def allows(self, task: str, now: float | None = None) -> bool:
        return (
            task in self.allowed_tasks
            and (permission_time() if now is None else now) < self.expires_at
        )


def task_policy(config: AgentConfig) -> TaskLease:
    value = _request(
        f"{config.core_url}/v1/gateway-agent/tasks", "GET", {}, _auth(config), config=config
    )
    if (
        not isinstance(value, dict)
        or set(value) != {"formatVersion", "nodeId", "allowedTasks", "leaseSeconds"}
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or value.get("nodeId") != config.node_id
        or type(value.get("leaseSeconds")) is not int
        or not 1 <= value["leaseSeconds"] <= 30
        or not isinstance(value.get("allowedTasks"), list)
        or len(value["allowedTasks"]) > 2
        or any(
            not isinstance(task, str) or task not in {"integration", "voice"}
            for task in value["allowedTasks"]
        )
        or len(set(value["allowedTasks"])) != len(value["allowedTasks"])
    ):
        raise CoreRequestError("E_AGENT_TASK_POLICY_INVALID")
    return TaskLease(frozenset(value["allowedTasks"]), permission_time() + value["leaseSeconds"])


@dataclass(frozen=True, slots=True)
class EnrollmentResult:
    node_id: str
    gateway_token: str


def prepared_capabilities(core_url: str, certificate: str, digest: str) -> dict[str, Any]:
    """Probe the actual restricted ingress before issuing a transferable code."""
    value = _request(
        f"{core_url.rstrip('/')}/v1/gateway-agent/enrollment-capabilities",
        "GET",
        {},
        tls=trusted_context(certificate, digest),
        local_only=True,
    )
    if (
        not isinstance(value, dict)
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or type(value.get("enrollmentProtocol")) is not int
        or value["enrollmentProtocol"] != 2
        or value.get("clientCredential") is not True
        or value.get("acknowledgementWithinOriginalExpiry") is not True
        or type(value.get("taskPolicyVersion")) is not int
        or value["taskPolicyVersion"] != 1
    ):
        raise CoreRequestError("E_AGENT_ENROLLMENT_UPGRADE_REQUIRED")
    return value


def enroll(
    core_url: str,
    enrollment_token: str,
    identity: dict[str, str],
    *,
    node_credential: str | None = None,
    ca_certificate: str | None = None,
    ca_sha256: str | None = None,
    agent_version: str | None = None,
) -> EnrollmentResult:
    context = None
    if node_credential is not None or ca_certificate is not None:
        if urlsplit(core_url).scheme != "https":
            raise CoreRequestError("E_AGENT_TLS_REQUIRED")
        context = trusted_context(ca_certificate, ca_sha256)
    if node_credential is not None:
        capability = _request(
            f"{core_url.rstrip('/')}/v1/gateway-agent/enrollment-capabilities",
            "GET",
            {},
            tls=context,
            local_only=True,
        )
        if (
            not isinstance(capability, dict)
            or type(capability.get("formatVersion")) is not int
            or capability["formatVersion"] != 1
            or type(capability.get("enrollmentProtocol")) is not int
            or capability["enrollmentProtocol"] != 2
            or capability.get("clientCredential") is not True
            or capability.get("acknowledgementWithinOriginalExpiry") is not True
        ):
            raise CoreRequestError("E_AGENT_ENROLLMENT_UPGRADE_REQUIRED")
    value = _request(
        f"{core_url.rstrip('/')}/v1/gateway-agent/enroll",
        "POST",
        {
            **identity,
            "enrollmentToken": enrollment_token,
            "agentVersion": agent_version or __version__,
            **({"nodeCredential": node_credential} if node_credential is not None else {}),
        },
        tls=context,
        local_only=node_credential is not None,
    )
    node_id = value.get("nodeId") if isinstance(value, dict) else None
    gateway_token = value.get("gatewayToken") if isinstance(value, dict) else None
    if not isinstance(node_id, str) or not isinstance(gateway_token, str):
        raise CoreRequestError("Core returned an invalid enrollment response")
    if node_credential is not None:
        try:
            valid_id = str(uuid.UUID(node_id)) == node_id
        except ValueError:
            valid_id = False
        if (
            not valid_id
            or not gateway_token.isascii()
            or not node_credential.isascii()
            or not hmac.compare_digest(gateway_token, node_credential)
        ):
            raise CoreRequestError("E_AGENT_ENROLLMENT_RESPONSE")
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
        config=config,
    )


def button_event(config: AgentConfig, device_id: str, action: str) -> None:
    _request(
        f"{config.core_url}/v1/gateway-agent/zigbee/button-events",
        "POST",
        {"deviceId": device_id, "action": action},
        _auth(config),
        expect_json=False,
        config=config,
    )


def motion_event(config: AgentConfig, device_id: str, detected: bool) -> None:
    _request(
        f"{config.core_url}/v1/gateway-agent/zigbee/motion-events",
        "POST",
        {"deviceId": device_id, "detected": detected},
        _auth(config),
        expect_json=False,
        config=config,
    )


def next_command(config: AgentConfig) -> dict[str, Any] | None:
    value = _request(
        f"{config.core_url}/v1/gateway-agent/commands/next",
        "POST",
        {},
        _auth(config),
        config=config,
    )
    return value if isinstance(value, dict) and isinstance(value.get("id"), str) else None


def complete_command(
    config: AgentConfig, command_id: str, succeeded: bool, error: str | None = None
) -> None:
    _request(
        f"{config.core_url}/v1/gateway-agent/commands/{command_id}/result",
        "POST",
        {"succeeded": succeeded, "error": error},
        _auth(config),
        expect_json=False,
        config=config,
    )


def _auth(config: AgentConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.gateway_token}", "X-Kyrion-Node-Id": config.node_id}


def _request(
    url: str,
    method: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    *,
    expect_json: bool = True,
    config: AgentConfig | None = None,
    tls: ssl.SSLContext | None = None,
    local_only: bool = False,
) -> Any:
    origin = urlsplit(url)
    if (
        origin.scheme not in {"http", "https"}
        or not origin.hostname
        or origin.username is not None
        or origin.password is not None
        or origin.fragment
        or origin.query
    ):
        raise CoreRequestError("E_AGENT_URL")
    if config is not None and config.ca_certificate is not None:
        if origin.scheme != "https":
            raise CoreRequestError("E_AGENT_TLS_REQUIRED")
        tls = trusted_context(config.ca_certificate, config.ca_sha256)
    local_only = local_only or (config is not None and config.local_only)
    if local_only and origin.scheme != "https":
        raise CoreRequestError("E_AGENT_TLS_REQUIRED")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = Request(
        url,
        data=None if method == "GET" else json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method=method,
    )
    try:
        handler = (
            LocalHTTPSHandler(tls or context_from_bytes(None))
            if local_only
            else HTTPSHandler(context=tls)
        )
        opener = build_opener(ProxyHandler({}), NoRedirect(), handler)
        with opener.open(request, timeout=10) as response:
            if not expect_json:
                return None
            raw = response.read(1024**2 + 1)
            if len(raw) > 1024**2:
                raise CoreRequestError("E_AGENT_RESPONSE_LIMIT")
            body = raw.decode("utf-8")
            return json.loads(body) if body else None
    except HTTPError as error:
        raise CoreRequestError(
            f"Core rejected the request with HTTP {error.code}", error.code
        ) from error
    except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError, UnicodeError) as error:
        raise CoreRequestError("Core is unavailable or returned invalid data") from error


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: HTTPResponse,
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        return None


@lru_cache(maxsize=8)
def context_from_bytes(certificate: bytes | None) -> ssl.SSLContext:
    return ssl.create_default_context(
        cadata=certificate.decode("ascii") if certificate is not None else None,
    )


def trusted_context(certificate: str | None, digest: str | None) -> ssl.SSLContext:
    if certificate is None:
        if digest is not None:
            raise CoreRequestError("E_AGENT_TLS_CONFIGURATION")
        return context_from_bytes(None)
    path = Path(certificate)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise CoreRequestError("E_AGENT_TLS_CONFIGURATION")
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024 or hashlib.sha256(raw).hexdigest() != digest:
        raise CoreRequestError("E_AGENT_TLS_CONFIGURATION")
    try:
        return context_from_bytes(raw)
    except (ssl.SSLError, UnicodeError, ValueError) as error:
        raise CoreRequestError("E_AGENT_TLS_CONFIGURATION") from error
