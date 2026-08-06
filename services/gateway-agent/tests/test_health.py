import os
import sys
from pathlib import Path

import pytest

from kyrion_gateway_agent.config import AgentConfig
from kyrion_gateway_agent.health import collect_health, platform_identity


def test_config_round_trip_uses_private_file_permissions(tmp_path: Path) -> None:
    path = tmp_path / "agent.json"
    expected = AgentConfig("http://core.local:8080", "node-id", "secret-token")

    expected.save(path)

    assert AgentConfig.load(path) == expected
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_health_contract_contains_bounded_platform_values() -> None:
    if sys.platform != "linux":
        pytest.skip("Linux system metrics are verified on the gateway target")
    health = collect_health()
    identity = platform_identity()

    assert health["memoryTotalBytes"] > 0
    assert 0 <= health["memoryAvailableBytes"] <= health["memoryTotalBytes"]
    assert health["storageTotalBytes"] > 0
    assert isinstance(health["services"], list)
    assert {service["id"] for service in health["services"]} == {
        "home-assistant", "matter", "mqtt", "otbr", "voice", "zigbee"
    }
    assert identity["hostname"]
    assert identity["architecture"]
