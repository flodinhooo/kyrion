"""Strict task-policy boundary and local lease expiry; synthetic Core responses."""

import uuid
from unittest.mock import patch

import pytest

from kyrion_gateway_agent import client
from kyrion_gateway_agent.config import AgentConfig

NODE = str(uuid.uuid4())
CONFIG = AgentConfig(
    "https://127.0.0.1:8443", NODE, "synthetic-private-credential", local_only=True
)


def policy(**changes):
    return {
        "formatVersion": 1,
        "nodeId": NODE,
        "allowedTasks": ["integration"],
        "leaseSeconds": 30,
        **changes,
    }


def test_tasks_expire_at_the_local_deadline_and_unknown_tasks_are_denied():
    with (
        patch.object(client, "_request", return_value=policy()) as request,
        patch.object(client, "permission_time", return_value=100),
    ):
        lease = client.task_policy(CONFIG)
    assert lease.allows("integration", 129.999)
    assert not lease.allows("integration", 130)
    assert not lease.allows("voice", 100)
    assert not lease.allows("local_ai", 100)
    assert request.call_args.kwargs["config"] is CONFIG


@pytest.mark.parametrize(
    "changes",
    [
        {"formatVersion": True},
        {"nodeId": str(uuid.uuid4())},
        {"leaseSeconds": True},
        {"leaseSeconds": 31},
        {"leaseSeconds": 0},
        {"leaseSeconds": "30"},
        {"allowedTasks": ["local_ai"]},
        {"allowedTasks": ["voice", "voice"]},
        {"allowedTasks": "voice"},
        {"allowedTasks": [None]},
        {"newAuthority": True},
    ],
)
def test_untrusted_or_future_policy_never_grants_authority(changes):
    with (
        patch.object(client, "_request", return_value=policy(**changes)),
        pytest.raises(client.CoreRequestError, match="E_AGENT_TASK_POLICY_INVALID"),
    ):
        client.task_policy(CONFIG)


def test_empty_assignment_grants_no_local_task():
    with patch.object(client, "_request", return_value=policy(allowedTasks=[])):
        lease = client.task_policy(CONFIG)
    assert not lease.allows("integration")
    assert not lease.allows("voice")
