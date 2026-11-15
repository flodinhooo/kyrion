"""Prepared runtime policy transitions with injected Core/OS boundaries."""

import threading
from unittest.mock import Mock, patch

import pytest

from kyrion_gateway_agent import client, prepared_runtime
from kyrion_gateway_agent.config import AgentConfig

CONFIG = AgentConfig(
    "https://127.0.0.1:8443", "fixture-node", "synthetic-credential", local_only=True
)


def test_valid_assignment_dispatches_an_existing_typed_command_once():
    stop = threading.Event()
    execute = Mock()
    command = {"id": "synthetic-command", "type": "synthetic-typed-action", "payload": {}}
    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(
            client,
            "task_policy",
            return_value=client.TaskLease(frozenset({"integration"}), float("inf")),
        ),
        patch.object(client, "next_command", side_effect=[command, None]),
        patch.object(client, "heartbeat", side_effect=lambda *_: stop.set()),
        patch.object(prepared_runtime, "collect_health", return_value={}) as health,
    ):
        prepared_runtime.run(CONFIG, execute, lambda *_: None, stop=stop)
    execute.assert_called_once_with(CONFIG, command)
    health.assert_called_once_with(include_integrations=True, include_voice=False)


def test_empty_tasks_report_only_basic_health_and_never_poll_commands():
    stop = threading.Event()
    execute = Mock()
    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(
            client, "task_policy", return_value=client.TaskLease(frozenset(), float("inf"))
        ),
        patch.object(client, "next_command") as commands,
        patch.object(client, "heartbeat", side_effect=lambda *_: stop.set()),
        patch.object(prepared_runtime, "collect_health", return_value={}) as health,
    ):
        prepared_runtime.run(CONFIG, execute, lambda *_: None, stop=stop)
    health.assert_called_once_with(include_integrations=False, include_voice=False)
    commands.assert_not_called()
    execute.assert_not_called()


def test_service_reports_connection_only_after_acknowledged_heartbeat():
    stop = threading.Event()
    states = []
    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(
            client, "task_policy", return_value=client.TaskLease(frozenset(), float("inf"))
        ),
        patch.object(client, "heartbeat", side_effect=lambda *_: stop.set()),
        patch.object(prepared_runtime, "collect_health", return_value={}),
    ):
        prepared_runtime.run(CONFIG, Mock(), lambda *_: None, stop=stop, report=states.append)
    assert states == ["connected", "stopped"]


def test_failed_heartbeat_never_reports_connected():
    stop = threading.Event()
    states = []

    def report(state):
        states.append(state)
        stop.set()

    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(
            client, "task_policy", return_value=client.TaskLease(frozenset(), float("inf"))
        ),
        patch.object(client, "heartbeat", side_effect=client.CoreRequestError("synthetic", 403)),
        patch.object(prepared_runtime, "collect_health", return_value={}),
        pytest.raises(client.CoreRequestError),
    ):
        prepared_runtime.run(CONFIG, Mock(), lambda *_: None, stop=stop, report=report)
    assert states == ["disconnected", "stopped"]


def test_expiring_lease_after_claim_fails_command_without_executing_it():
    stop = threading.Event()
    execute = Mock()
    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(
            client, "task_policy", return_value=client.TaskLease(frozenset({"integration"}), 130)
        ),
        patch.object(client, "permission_time", side_effect=[100, 100, 131, 131]),
        patch.object(client, "next_command", return_value={"id": "synthetic-command"}),
        patch.object(client, "complete_command") as complete,
        patch.object(client, "heartbeat", side_effect=lambda *_: stop.set()),
        patch.object(prepared_runtime, "collect_health", return_value={}),
    ):
        prepared_runtime.run(CONFIG, execute, lambda *_: None, stop=stop)
    execute.assert_not_called()
    complete.assert_called_once_with(CONFIG, "synthetic-command", False, "TASK_LEASE_EXPIRED")


@pytest.mark.parametrize("status", [401, 403, 404, 405])
def test_revoked_or_unsupported_authority_exits_instead_of_falling_back(status):
    stop = threading.Event()
    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(
            client, "task_policy", side_effect=client.CoreRequestError("synthetic", status)
        ),
        patch.object(client, "next_command") as commands,
        patch.object(prepared_runtime, "collect_health") as health,
        pytest.raises(client.CoreRequestError),
    ):
        prepared_runtime.run(CONFIG, Mock(), lambda *_: None, stop=stop)
    assert stop.is_set()
    commands.assert_not_called()
    health.assert_not_called()


def test_transport_failure_clears_authority_before_bounded_retry():
    stop = threading.Event()
    waiting = []
    gates = []

    def retry(delay):
        waiting.append(delay)
        stop.set()
        return True

    def observe(_config, allows, _stop, _register):
        gates.append(allows)

    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(
            client,
            "task_policy",
            return_value=client.TaskLease(frozenset({"integration"}), float("inf")),
        ),
        patch.object(client, "next_command", return_value=None),
        patch.object(client, "heartbeat", side_effect=client.CoreRequestError("offline")),
        patch.object(prepared_runtime, "collect_health", return_value={}),
        patch.object(stop, "wait", side_effect=retry),
    ):
        prepared_runtime.run(CONFIG, Mock(), observe, stop=stop)
    assert waiting == [2]
    assert len(gates) == 1
    assert not gates[0]()


def test_a_child_registered_after_stop_is_still_terminated():
    stop = threading.Event()
    stop.set()
    child = Mock()
    child.poll.return_value = None
    child.terminate.side_effect = lambda: setattr(child.poll, "return_value", 0)

    def late(_config, _allows, _stop, register):
        register(child)

    with patch.object(prepared_runtime.sys, "platform", "linux"):
        prepared_runtime.run(CONFIG, Mock(), late, stop=stop)
    child.terminate.assert_called_once()
    child.wait.assert_called_once_with(timeout=1)


@pytest.mark.parametrize("code", ["E_AGENT_TLS_CONFIGURATION", "E_AGENT_TASK_POLICY_INVALID"])
def test_invalid_trust_or_policy_is_not_treated_as_a_transient_disconnect(code):
    stop = threading.Event()
    with (
        patch.object(prepared_runtime.sys, "platform", "linux"),
        patch.object(client, "task_policy", side_effect=client.CoreRequestError(code)),
        patch.object(stop, "wait") as retry,
        pytest.raises(client.CoreRequestError, match=code),
    ):
        prepared_runtime.run(CONFIG, Mock(), lambda *_: None, stop=stop)
    retry.assert_not_called()
