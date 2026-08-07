from unittest.mock import Mock, patch

import pytest

from kyrion_gateway_agent import cli
from kyrion_gateway_agent.client import CoreRequestError
from kyrion_gateway_agent.config import AgentConfig


def test_run_polls_commands_between_heartbeats(monkeypatch: pytest.MonkeyPatch) -> None:
    config = AgentConfig("http://core.local:8080", "node-id", "secret-token")
    monkeypatch.setattr(AgentConfig, "load", Mock(return_value=config))
    monotonic = iter([0.0, 0.25, 0.5])
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(monotonic))
    sleep = Mock(side_effect=[None, None, KeyboardInterrupt])
    monkeypatch.setattr(cli.time, "sleep", sleep)

    with patch.object(cli, "next_command", return_value=None) as next_command, \
         patch.object(cli, "heartbeat") as heartbeat, \
         patch.object(cli, "collect_health", return_value={}), \
         patch("sys.argv", ["agent", "run", "--interval", "5", "--command-interval", "0.25"]), \
         pytest.raises(KeyboardInterrupt):
        cli.main()

    assert next_command.call_count == 3
    heartbeat.assert_called_once_with(config, {})
    assert sleep.call_args_list[0].args == (0.25,)


def test_run_backs_off_when_core_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    config = AgentConfig("http://core.local:8080", "node-id", "secret-token")
    monkeypatch.setattr(AgentConfig, "load", Mock(return_value=config))
    sleep = Mock(side_effect=KeyboardInterrupt)
    monkeypatch.setattr(cli.time, "sleep", sleep)

    with patch.object(cli, "next_command", side_effect=CoreRequestError("offline")), \
         patch("sys.argv", ["agent", "run", "--interval", "5"]), \
         pytest.raises(KeyboardInterrupt):
        cli.main()

    sleep.assert_called_once_with(5)


def test_hue_recover_command_is_bounded_to_the_device_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AgentConfig("http://core.local:8080", "node-id", "secret-token")
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(cli.subprocess, "run", run)
    completed = Mock()
    monkeypatch.setattr(cli, "complete_command", completed)

    cli._execute_command(config, {
        "id": "command-id",
        "type": "zigbee.hue_power_on_recover",
        "payload": {"deviceId": "0x001788010fdcc07d"},
    })

    arguments = run.call_args.args[0]
    assert arguments[4] == "zigbee2mqtt/0x001788010fdcc07d/set"
    assert arguments[6] == '{"hue_power_on_behavior": "recover"}'
    completed.assert_called_once_with(config, "command-id", True)


def test_zigbee_remove_uses_bounded_bridge_request(monkeypatch: pytest.MonkeyPatch) -> None:
    config = AgentConfig("http://core.local:8080", "node-id", "secret-token")
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(cli.subprocess, "run", run)
    completed = Mock()
    monkeypatch.setattr(cli, "complete_command", completed)

    cli._execute_command(config, {
        "id": "command-id",
        "type": "zigbee.remove",
        "payload": {"deviceId": "0x001788010fdcc07d"},
    })

    arguments = run.call_args.args[0]
    assert arguments[4] == "zigbee2mqtt/bridge/request/device/remove"
    assert arguments[6] == '{"id": "0x001788010fdcc07d", "force": true}'
    completed.assert_called_once_with(config, "command-id", True)
