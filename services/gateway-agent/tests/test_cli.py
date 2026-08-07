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
