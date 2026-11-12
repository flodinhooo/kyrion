"""Actual Core/SQL/TLS linked setup driven by isolated terminal input fixtures."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from linked_onboarding import linked_setup
from onboarding import CoreClient
from runtime import Installation


def exercise_linked_account(request, root, ports, provider):
    # This is an unprivileged protocol fixture, not SCM acceptance. Use the same
    # private user-temp policy as native journal unit tests, rather than adopting
    # a workspace parent's administrator-owned primary group.
    with tempfile.TemporaryDirectory(prefix="kyrion-linked-journal-") as directory:
        return _exercise_linked_account(
            request, root, ports, provider, Path(directory) / "installation"
        )


def _exercise_linked_account(request, root, ports, provider, target):
    bootstrap = (root / "bootstrap").read_text()

    def refused(statuses, method, route, body=None, secret=None, auth=None):
        try:
            request(method, route, body, token=auth, bootstrap=secret)
        except HTTPError as error:
            if error.code not in statuses:
                raise ValueError("E_LINKED_FIXTURE_WRONG_REJECTION") from None
        else:
            raise ValueError("E_LINKED_FIXTURE_UNEXPECTED_ADMISSION")

    refused({403}, "POST", "/v1/auth/central/setup/start")
    provider.device_lifetime = 1
    expired = request("POST", "/v1/auth/central/setup/start", bootstrap=bootstrap)
    time.sleep(1.2)
    refused(
        {400},
        "POST",
        "/v1/auth/central/setup/poll",
        {"operationToken": expired["operationToken"]},
        bootstrap,
    )
    provider.device_lifetime = 600
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
    invitation = request("POST", "/v1/space/invitations", {}, token=token)
    registration = request(
        "POST",
        "/v1/auth/central/registration/start",
        {"invitationCode": invitation["code"]},
    )
    time.sleep(registration["interval"])
    registration_body = {"operationToken": registration["operationToken"]}
    request("POST", "/v1/auth/central/registration/poll", registration_body)
    refused(
        {409},
        "POST",
        "/v1/auth/central/registration/complete",
        {
            **registration_body,
            "confirm": True,
            "credentials": {
                "username": "duplicate-identity-probe",
                "password": credentials["password"],
                "invitationCode": invitation["code"],
            },
        },
    )
    invitations = request("GET", "/v1/space/invitations", token=token)
    retained = next(item for item in invitations if item["id"] == invitation["id"])
    if retained["useCount"] != 0 or retained["status"] != "ACTIVE":
        raise ValueError("E_LINKED_FIXTURE_INVITATION_ROLLBACK")
    provider.subject = "synthetic-linked-member"
    try:
        with (
            patch(
                "builtins.input",
                side_effect=[
                    "ONLINE",
                    "CHECK",
                    "JOIN",
                    "",
                    "CHECK",
                    "fixture-member",
                    "USE",
                ],
            ),
            patch(
                "linked_onboarding.getpass.getpass",
                side_effect=[
                    invitation["code"],
                    "Synthetic-member-password-123456",
                    "Synthetic-member-password-123456",
                ],
            ),
            patch("builtins.print"),
        ):
            member = linked_setup(client, messages)
        if (
            member["id"] == owner_id
            or "OWNER" in member["roles"]
            or member["space"]["id"] != owner_id
        ):
            raise ValueError("E_LINKED_FIXTURE_INVITATION_ROLE")
        refused(
            {403},
            "PUT",
            "/v1/space",
            {"name": "Must not rename", "type": "HOME"},
            auth=client.session,
        )
    finally:
        client.close()
    provider.subject = "synthetic-spent-invitation-probe"
    replay = request(
        "POST",
        "/v1/auth/central/registration/start",
        {"invitationCode": invitation["code"]},
    )
    time.sleep(replay["interval"])
    replay_body = {"operationToken": replay["operationToken"]}
    request("POST", "/v1/auth/central/registration/poll", replay_body)
    refused(
        {400},
        "POST",
        "/v1/auth/central/registration/complete",
        {
            **replay_body,
            "confirm": True,
            "credentials": {
                "username": "spent-invitation-probe",
                "password": credentials["password"],
                "invitationCode": invitation["code"],
            },
        },
    )
    provider.subject = "synthetic-linked-owner"
    return (
        credentials,
        token,
        owner_id,
        {
            "linkedFirstOwner": True,
            "authorizedBusinessSpace": True,
            "existingLinkedIdentityReused": True,
            "pendingAndCancelledProof": True,
            "expiredProofRejected": True,
            "setupTransactionRollback": True,
            "consumedFailedProof": True,
            "unmappedAccountDenied": True,
            "syntheticOidcProvider": True,
            "providerTlsVerified": True,
            "invitationMemberJoinedExistingSpace": True,
            "invitationRolePreserved": True,
            "duplicateIdentityRolledBackInvitation": True,
            "spentInvitationRejected": True,
            "memberCannotAdministerSpace": True,
        },
    )
