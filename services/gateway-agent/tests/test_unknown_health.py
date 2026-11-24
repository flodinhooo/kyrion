"""Explicit protocol doubles for the unknown-health compatibility fence."""

import uuid
from unittest.mock import patch

import pytest

from kyrion_gateway_agent import client
from kyrion_gateway_agent.config import AgentConfig


@pytest.mark.parametrize("version", [None, True, "1", 0, 2])
def test_old_core_never_receives_unknown_booleans(version):
    config = AgentConfig("https://localhost", str(uuid.uuid4()), "synthetic", local_only=True)
    with (
        patch.object(
            client, "prepared_capabilities", return_value={"healthUnknownVersion": version}
        ),
        patch.object(client, "_request") as request,
        pytest.raises(client.CoreRequestError, match="E_AGENT_HEALTH_UPGRADE_REQUIRED"),
    ):
        client.heartbeat(config, {"throttled": None})
    request.assert_not_called()


def test_compatible_prepared_core_receives_explicit_null_without_coercion():
    config = AgentConfig("https://localhost", str(uuid.uuid4()), "synthetic", local_only=True)
    health = {"throttled": None, "ethernet": {"present": None, "connected": None}}
    with (
        patch.object(client, "prepared_capabilities", return_value={"healthUnknownVersion": 1}),
        patch.object(client, "_request") as request,
    ):
        client.heartbeat(config, health)
    assert request.call_args.args[1:3] == ("PUT", {"health": health})


def test_legacy_transport_cannot_send_unknown_health():
    config = AgentConfig("http://localhost", str(uuid.uuid4()), "synthetic")
    with patch.object(client, "_request") as request, pytest.raises(client.CoreRequestError):
        client.heartbeat(config, {"ipv6": None})
    request.assert_not_called()
