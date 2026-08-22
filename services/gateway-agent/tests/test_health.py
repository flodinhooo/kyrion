import os
import sys
from pathlib import Path

import pytest

from kyrion_gateway_agent import health as health_module
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
    assert isinstance(health["adapters"], list)
    assert {service["id"] for service in health["services"]} == {
        "home-assistant", "matter", "mqtt", "otbr", "voice", "zigbee"
    }
    assert identity["hostname"]
    assert identity["architecture"]


def test_zigbee_health_reports_sensor_values(monkeypatch) -> None:
    devices = (
        '[{"type":"EndDevice","friendly_name":"hall-motion",'
        '"ieee_address":"0x00124b0024abcdef","supported":true,'
        '"definition":{"vendor":"SONOFF","model":"SNZB-03P",'
        '"description":"Motion sensor"}}]'
    )
    info = '{"permit_join":false,"network":{"channel":15}}'
    responses = iter([devices, info])
    monkeypatch.setattr(health_module, "_command", lambda _command, _default: next(responses))
    monkeypatch.setattr(
        health_module,
        "_zigbee_device_state",
        lambda _name: '{"occupancy":true,"battery":87,"illuminance":42,"linkquality":155}',
    )

    health = health_module._zigbee_health()

    assert health is not None
    assert health["devices"][0] | {"friendlyName": "hall-motion"} == health["devices"][0]
    assert health["devices"][0]["occupancy"] is True
    assert health["devices"][0]["battery"] == 87
    assert health["devices"][0]["illuminance"] == 42


def test_audio_endpoint_reports_only_the_expected_pipewire_direction(monkeypatch) -> None:
    source = """
      * media.class = "Audio/Source"
        device.api = "alsa"
      * node.description = "Microphone(Delock 20672) Mono"
      * node.name = "alsa_input.usb-0c76_Microphone_Delock_20672_-00.mono-fallback"
    """
    monkeypatch.setattr(health_module, "_command", lambda _command, _default: source)

    assert health_module._audio_endpoint("@DEFAULT_AUDIO_SOURCE@", "capture") == {
        "id": "alsa_input.usb-0c76_Microphone_Delock_20672_-00.mono-fallback",
        "displayName": "Microphone(Delock 20672) Mono",
        "transport": "usb",
    }
    assert health_module._audio_endpoint("@DEFAULT_AUDIO_SOURCE@", "playback") is None
