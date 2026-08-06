from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentConfig:
    core_url: str
    node_id: str
    gateway_token: str

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
        return cls(core_url.rstrip("/"), node_id, gateway_token)

    def save(self, path: Path) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)


DEFAULT_CONFIG_PATH = Path(os.getenv("KYRION_GATEWAY_CONFIG", "/etc/kyrion-gateway/agent.json"))
