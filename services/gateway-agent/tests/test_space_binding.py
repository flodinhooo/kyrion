"""Enrollment protocol boundary tests; no target OS or real Core acceptance claims."""

import secrets
import sys
import uuid
from unittest.mock import patch

import pytest

from kyrion_gateway_agent import client


def claim(space):
    return client.enroll(
        "https://localhost:8443",
        secrets.token_urlsafe(32),
        {},
        node_credential=secrets.token_urlsafe(32),
        expected_space_id=space,
    )


def capability(version):
    return {
        "formatVersion": 1,
        "enrollmentProtocol": 2,
        "clientCredential": True,
        "acknowledgementWithinOriginalExpiry": True,
        "spaceBindingVersion": version,
    }


@pytest.mark.parametrize("version", [None, True, "1", 0, 2])
def test_incompatible_core_never_receives_one_use_code(version):
    with (
        patch.object(client, "trusted_context"),
        patch.object(client, "_request", return_value=capability(version)) as request,
        pytest.raises(client.CoreRequestError, match="E_AGENT_SPACE_BINDING_REQUIRED"),
    ):
        claim(str(uuid.uuid4()))
    assert request.call_count == 1
    assert request.call_args.args[1] == "GET"


@pytest.mark.parametrize("returned", [None, "invalid", str(uuid.uuid4()), 1])
def test_missing_or_wrong_actual_space_is_not_success(returned):
    space = str(uuid.uuid4())

    def response(url, method, body=None, **options):
        if method == "GET":
            return capability(1)
        assert body["expectedSpaceId"] == space
        return {
            "nodeId": str(uuid.uuid4()),
            "gatewayToken": body["nodeCredential"],
            "spaceId": returned,
        }

    with (
        patch.object(client, "trusted_context"),
        patch.object(client, "_request", side_effect=response),
        pytest.raises(client.CoreRequestError, match="E_AGENT_SPACE_BINDING_RESPONSE"),
    ):
        claim(space)


def test_verified_actual_space_is_retained():
    space = str(uuid.uuid4())

    def response(url, method, body=None, **options):
        if method == "GET":
            return capability(1)
        return {
            "nodeId": str(uuid.uuid4()),
            "gatewayToken": body["nodeCredential"],
            "spaceId": space,
        }

    with (
        patch.object(client, "trusted_context"),
        patch.object(client, "_request", side_effect=response),
    ):
        assert claim(space).space_id == space


@pytest.mark.skipif(sys.platform != "win32", reason="Actual native Windows lease clock")
def test_native_windows_permission_clock_and_expired_lease():
    import ctypes

    clock = ctypes.WinDLL("kernel32").GetTickCount64
    clock.argtypes = []
    clock.restype = ctypes.c_ulonglong
    before = clock() / 1000
    observed = client.permission_time()
    after = clock() / 1000
    assert before <= observed <= after
    lease = client.TaskLease(frozenset({"integrations"}), observed + 30)
    assert lease.allows("integrations", observed + 29)
    assert not lease.allows("integrations", observed + 30)
