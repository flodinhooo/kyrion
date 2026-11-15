"""Enumerated local agent ingress on the existing verified TLS listener."""

from __future__ import annotations

import json
import re
from pathlib import Path

AGENT_PATHS = (
    "/v1/gateway-agent/enrollment-capabilities",
    "/v1/gateway-agent/tasks",
    "/v1/gateway-agent/enroll",
    "/v1/gateway-agent/heartbeat",
    "/v1/gateway-agent/commands/next",
    "/v1/gateway-agent/commands/*/result",
    "/v1/gateway-agent/zigbee/button-events",
    "/v1/gateway-agent/zigbee/motion-events",
    "/v1/voice-satellite/enroll",
    "/v1/voice-satellite/bootstrap-from-gateway",
    "/v1/voice-satellite/sessions",
    "/v1/voice-satellite/sessions/close",
    "/v1/voice-satellite/sessions/*/greeting",
    "/v1/voice-satellite/sessions/*/turns",
    "/v1/voice-satellite/sessions/*/turns/*/playback-completed",
    "/v1/voice-satellite/sessions/*/turns/*/execute",
)
LOCAL_PEERS = "127.0.0.0/8 ::1/128 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 fc00::/7"


def agent_handle(upstream: str, certificate: Path | None = None) -> str:
    native = re.fullmatch(r"https://127\.0\.0\.1:([1-9][0-9]{0,4})", upstream)
    if upstream != "core:8080" and (native is None or int(native.group(1)) > 65535):
        raise ValueError("E_AGENT_PROXY_UPSTREAM")
    if (native is not None) != (certificate is not None):
        raise ValueError("E_AGENT_PROXY_TRUST")
    transport = ""
    if certificate is not None:
        if not certificate.is_absolute() or any(
            char in str(certificate) for char in "\r\n\x00"
        ):
            raise ValueError("E_AGENT_PROXY_TRUST")
        transport = (
            " {\n    transport http {\n      tls_trust_pool file "
            + json.dumps(certificate.as_posix())
            + "\n    }\n  }"
        )
    return (
        "  @kyrion_agent path " + " ".join(AGENT_PATHS) + "\n"
        "  handle @kyrion_agent {\n"
        "    @kyrion_nonlocal not remote_ip " + LOCAL_PEERS + "\n"
        "    respond @kyrion_nonlocal 403\n"
        "    reverse_proxy " + upstream + transport + "\n"
        "  }\n"
    )
