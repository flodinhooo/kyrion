"""Ingress protocol validation with the HTTP operation explicitly injected."""

from unittest.mock import patch

import pytest

from kyrion_gateway_agent import client

VALID = {
    "formatVersion": 1,
    "enrollmentProtocol": 2,
    "clientCredential": True,
    "acknowledgementWithinOriginalExpiry": True,
    "taskPolicyVersion": 1,
}


def test_probe_uses_pinned_local_only_transport_without_owner_credentials():
    with (
        patch.object(client, "trusted_context", return_value="synthetic TLS context"),
        patch.object(client, "_request", return_value=VALID) as operation,
    ):
        assert (
            client.prepared_capabilities("https://fixture.test", "/synthetic/ca", "a" * 64) == VALID
        )
    operation.assert_called_once_with(
        "https://fixture.test/v1/gateway-agent/enrollment-capabilities",
        "GET",
        {},
        tls="synthetic TLS context",
        local_only=True,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"taskPolicyVersion": True},
        {"taskPolicyVersion": 0},
        {"enrollmentProtocol": 1},
        {"clientCredential": False},
    ],
)
def test_incomplete_or_old_ingress_protocol_refused(change):
    with (
        patch.object(client, "trusted_context"),
        patch.object(client, "_request", return_value={**VALID, **change}),
        pytest.raises(client.CoreRequestError),
    ):
        client.prepared_capabilities("https://fixture.test", "/synthetic/ca", "a" * 64)
