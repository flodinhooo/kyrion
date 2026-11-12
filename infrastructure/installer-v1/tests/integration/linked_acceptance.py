"""Actual Core/SQL/TLS linked setup driven by isolated terminal input fixtures."""

import json
import time
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from linked_onboarding import linked_setup
from onboarding import CoreClient
from runtime import Installation


def exercise_linked_account(request, root, ports, provider):
    bootstrap = (root / "bootstrap").read_text()

    def refused(statuses, method, route, body=None, secret=None):
        try:
            request(method, route, body, bootstrap=secret)
        except HTTPError as error:
            if error.code not in statuses:
                raise ValueError("E_LINKED_FIXTURE_WRONG_REJECTION") from None
        else:
            raise ValueError("E_LINKED_FIXTURE_UNEXPECTED_ADMISSION")

    refused({403}, "POST", "/v1/auth/central/setup/start")
    operation = request("POST", "/v1/auth/central/setup/start", bootstrap=bootstrap)
    time.sleep(operation["interval"])
    body = {"operationToken": operation["operationToken"]}
    if (
        request("POST", "/v1/auth/central/setup/poll", body, bootstrap=bootstrap)[
            "status"
        ]
        != "PENDING"
    ):
        raise ValueError("E_LINKED_FIXTURE_CONSENT")
    request("POST", "/v1/auth/central/setup/cancel", body, bootstrap=bootstrap)
    refused({400}, "POST", "/v1/auth/central/setup/poll", body, bootstrap)

    provider.approved = True  # Deliberate synthetic provider consent; no real account.
    operation = request("POST", "/v1/auth/central/setup/start", bootstrap=bootstrap)
    time.sleep(operation["interval"])
    body = {"operationToken": operation["operationToken"]}
    if (
        request("POST", "/v1/auth/central/setup/poll", body, bootstrap=bootstrap)[
            "status"
        ]
        != "CONFIRM"
    ):
        raise ValueError("E_LINKED_FIXTURE_PROOF")
    credentials = {
        "username": "fixture-owner",
        "password": "Synthetic-local-password-123456",
    }
    invalid = {
        **body,
        "confirm": True,
        "credentials": {**credentials, "spaceType": "BUSINESS", "spaceName": "\u0001"},
    }
    refused({400}, "POST", "/v1/auth/central/setup/complete", invalid, bootstrap)
    if request("GET", "/v1/auth/setup/status")["setupRequired"] is not True:
        raise ValueError("E_LINKED_FIXTURE_PARTIAL_OWNER")
    invalid["credentials"]["spaceName"] = "Must not create a second attempt"
    refused({400}, "POST", "/v1/auth/central/setup/complete", invalid, bootstrap)

    target = root / "installer-state"
    installation = Installation(
        target,
        {"release": "1.2.3", "architecture": "windows/amd64"},
        "a" * 64,
        "fixture.test",
        "127.0.0.1",
    )
    installation.state["backend"] = "windows-native"
    installation.save()
    installation.write(
        "installer.exe", b"unused synthetic journal marker; never executed"
    )
    installation.write("native-manifest.json", "{}")
    installation.write("secrets/bootstrap.secret", bootstrap)
    installation.write("core-cert.pem", (root / "core-cert.pem").read_bytes())
    installation.write(
        "native-runtime.json",
        json.dumps(
            {
                "formatVersion": 1,
                "hostname": "fixture.test",
                "address": "127.0.0.1",
                "ports": ports,
            }
        ),
    )
    client = CoreClient(installation)
    messages = json.loads(
        (Path(__file__).resolve().parents[2] / "locales/en.json").read_text()
    )
    try:
        with (
            patch(
                "builtins.input",
                side_effect=[
                    "CHECK",
                    credentials["username"],
                    "BUSINESS",
                    "Linked developer Space",
                    "USE",
                ],
            ),
            patch(
                "linked_onboarding.getpass.getpass",
                return_value=credentials["password"],
            ),
            patch("builtins.print"),
        ):
            user = linked_setup(client, messages)
        owner_id = user["id"]
        if (
            "OWNER" not in user["roles"]
            or installation.state["selectedSpace"]["type"] != "BUSINESS"
        ):
            raise ValueError("E_LINKED_FIXTURE_SPACE")
        persisted = (target / "install-state.json").read_text()
        if (
            credentials["password"] in persisted
            or client.session in persisted
            or provider.subject in persisted
        ):
            raise ValueError("E_LINKED_FIXTURE_SECRET_JOURNAL")
        client.close()
        with (
            patch("builtins.input", side_effect=["ONLINE", "CHECK", "USE"]),
            patch("builtins.print"),
        ):
            existing = linked_setup(client, messages)
        if existing["id"] != owner_id:
            raise ValueError("E_LINKED_FIXTURE_CHANGED_IDENTITY")
        token = client.session
        # Session intentionally remains in the caller for its independent probes.
        client.session = None
    finally:
        client.close()
    provider.subject = "unmapped-synthetic-account"
    operation = request("POST", "/v1/auth/central/start", {"mode": "LOGIN"})
    time.sleep(operation["interval"])
    body = {"operationToken": operation["operationToken"]}
    request("POST", "/v1/auth/central/poll", body)
    refused({403}, "POST", "/v1/auth/central/complete", {**body, "confirm": True})
    provider.subject = "synthetic-linked-owner"
    return (
        credentials,
        token,
        {
            "linkedFirstOwner": True,
            "authorizedBusinessSpace": True,
            "existingLinkedIdentityReused": True,
            "pendingAndCancelledProof": True,
            "setupTransactionRollback": True,
            "consumedFailedProof": True,
            "unmappedAccountDenied": True,
            "syntheticOidcProvider": True,
            "providerTlsVerified": True,
        },
    )
