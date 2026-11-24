from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentConfig:
    core_url: str
    node_id: str
    gateway_token: str = field(repr=False)
    ca_certificate: str | None = None
    ca_sha256: str | None = None
    local_only: bool = False
    space_id: str | None = None

    @classmethod
    def load(cls, path: Path) -> AgentConfig:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Agent configuration must be an object")
        core_url = value.get("core_url")
        node_id = value.get("node_id")
        gateway_token = value.get("gateway_token")
        if not all(isinstance(item, str) and item for item in (core_url, node_id, gateway_token)):
            raise ValueError("Agent configuration is incomplete")
        if not core_url.startswith(("http://", "https://")):
            raise ValueError("Core URL must use HTTP or HTTPS")
        certificate, digest = value.get("ca_certificate"), value.get("ca_sha256")
        local_only = value.get("local_only", False)
        if type(local_only) is not bool or (local_only and not core_url.startswith("https://")):
            raise ValueError("E_AGENT_TLS_CONFIGURATION")
        if (certificate is not None or digest is not None) and (
            not isinstance(certificate, str)
            or not Path(certificate).is_absolute()
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or not core_url.startswith("https://")
        ):
            raise ValueError("E_AGENT_TLS_CONFIGURATION")
        space_id = value.get("space_id")
        if space_id is not None:
            try:
                valid_space = isinstance(space_id, str) and str(uuid.UUID(space_id)) == space_id
            except ValueError:
                valid_space = False
            if not valid_space:
                raise ValueError("E_AGENT_SPACE_BINDING_INVALID")
        return cls(
            core_url.rstrip("/"), node_id, gateway_token, certificate, digest, local_only, space_id
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)


DEFAULT_CONFIG_PATH = Path(os.getenv("KYRION_GATEWAY_CONFIG", "/etc/kyrion-gateway/agent.json"))
