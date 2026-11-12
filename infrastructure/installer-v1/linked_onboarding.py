"""Normal linked onboarding through Core; no installer accounts or memberships."""

from __future__ import annotations

import datetime
import getpass
import json
import re
import time
import uuid
import webbrowser
from contextlib import contextmanager
from urllib.parse import urlsplit


@contextmanager
def provider_proof(
    client,
    messages,
    fresh: bool,
    invitation: str | None = None,
    mode: str = "LOGIN",
    current_password: str | None = None,
):
    secret = (
        (client.installation.target / "secrets/bootstrap.secret").read_text().strip()
        if fresh
        else None
    )
    prefix = "/v1/auth/central/setup" if fresh else "/v1/auth/central"
    start_body = None if fresh else {"mode": "LOGIN"}
    if mode == "LINK":
        if (
            fresh
            or invitation is not None
            or client.session is None
            or current_password is None
        ):
            raise ValueError("E_IDENTITY_OPERATION")
        start_body = {"mode": "LINK", "currentPassword": current_password}
    elif mode != "LOGIN":
        raise ValueError("E_IDENTITY_OPERATION")
    if invitation is not None:
        if fresh or not re.fullmatch(r"[A-Za-z0-9_-]{43}", invitation):
            raise ValueError("E_INVITATION")
        prefix = "/v1/auth/central/registration"
        start_body = {"invitationCode": invitation}
    operation = client.request(
        "POST",
        prefix + "/start",
        start_body,
        bootstrap=secret,
    )
    token = operation.get("operationToken")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError("E_IDENTITY_OPERATION")
    completed = False
    try:
        uri = operation["verificationUri"]
        url = urlsplit(uri)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.fragment
        ):
            raise ValueError("E_IDENTITY_URI")
        expiry = datetime.datetime.fromisoformat(
            operation["expiresAt"].replace("Z", "+00:00")
        )
        remaining = (expiry - datetime.datetime.now(datetime.UTC)).total_seconds()
        interval = operation["interval"]
        code = operation.get("userCode")
        if not isinstance(code, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 -]{0,127}", code
        ):
            raise ValueError("E_IDENTITY_OPERATION")
        if (
            not 0 < remaining <= 601
            or type(interval) is not int
            or not 1 <= interval <= 60
        ):
            raise ValueError("E_IDENTITY_OPERATION")
        print(messages["centralBrowser"])
        print(uri)
        print(messages["centralCode"] + ": " + code)
        action = (
            input(messages["centralOpen"] + " [OPEN/CHECK/CANCEL]: ").strip().upper()
        )
        if action == "OPEN":
            webbrowser.open(uri, new=2)
        elif action != "CHECK":
            raise ValueError("E_IDENTITY_CANCELLED")
        deadline = time.monotonic() + min(600, remaining)
        while time.monotonic() < deadline:
            time.sleep(interval)
            status = client.request(
                "POST", prefix + "/poll", {"operationToken": token}, bootstrap=secret
            )
            if status.get("status") == "CONFIRM":
                yield token, secret, prefix
                completed = True
                return
            if status.get("status") != "PENDING":
                raise ValueError("E_IDENTITY_OPERATION")
        raise ValueError("E_IDENTITY_EXPIRED")
    finally:
        if not completed:
            try:
                client.request(
                    "POST",
                    prefix + "/cancel",
                    {"operationToken": token},
                    bootstrap=secret,
                )
            except (OSError, ValueError):
                pass  # Preserve the original failure; Core expires abandoned proofs.


def adopt_session(client, response):
    token = response.get("sessionToken") if isinstance(response, dict) else None
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError("E_IDENTITY_SESSION")
    client.session = token
    user = client.request("GET", "/v1/auth/me")
    if client.request("GET", "/v1/auth/central/status").get("linked") is not True:
        raise ValueError("E_IDENTITY_LINK_REQUIRED")
    return user


def resolve_existing_access(client, messages):
    action = (
        input(messages["spaceInvitationChoice"] + " [LINK/JOIN/CANCEL]: ")
        .strip()
        .upper()
    )
    if action == "LINK":
        return connect_local_account(client, messages, confirmed=True)
    if action != "JOIN":
        raise ValueError("E_IDENTITY_CANCELLED")
    invitation = getpass.getpass(messages["spaceInvitationCode"] + ": ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", invitation):
        raise ValueError("E_INVITATION")
    email = input(messages["spaceInvitationEmail"] + ": ").strip()
    proof = None
    if email:
        client.request(
            "POST",
            "/v1/auth/registration-email",
            {"invitationCode": invitation, "email": email},
        )
        proof = getpass.getpass(messages["spaceInvitationEmailProof"] + ": ").strip()
    with provider_proof(client, messages, False, invitation) as (token, _, prefix):
        print(messages["linkedOfflineIdentity"])
        print(messages["offlineIdentityPolicy"])
        username = input(messages["localUsername"] + ": ").strip()
        password = getpass.getpass(messages["localPassword"] + ": ")
        if password != getpass.getpass(messages["repeatPassword"] + ": "):
            raise ValueError("E_PASSWORD_MISMATCH")
        credentials = {
            "username": username,
            "password": password,
            "invitationCode": invitation,
            "email": email or None,
            "emailProof": proof,
        }
        del password
        try:
            response = client.request(
                "POST",
                prefix + "/complete",
                {"operationToken": token, "confirm": True, "credentials": credentials},
            )
        finally:
            credentials.pop("password", None)
        return adopt_session(client, response)


def connect_local_account(client, messages, user=None, password=None, confirmed=False):
    if (
        not confirmed
        and input(messages["linkExistingLocal"] + " [LINK/CANCEL]: ").strip().upper()
        != "LINK"
    ):
        raise ValueError("E_IDENTITY_LINK_REQUIRED")
    if client.request("GET", "/v1/auth/central/config").get("enabled") is not True:
        raise ValueError("E_IDENTITY_NOT_CONFIGURED")
    if user is None:
        username = input(messages["localUsername"] + ": ").strip()
        password = getpass.getpass(messages["localPassword"] + ": ")
        user = client.login_or_setup(username, password)
    if client.request("GET", "/v1/auth/central/status").get("linked") is True:
        raise ValueError("E_IDENTITY_ALREADY_LINKED")
    with provider_proof(
        client, messages, False, mode="LINK", current_password=password
    ) as (token, _, prefix):
        response = client.request(
            "POST", prefix + "/complete", {"operationToken": token, "confirm": True}
        )
        if response.get("linked") is not True:
            raise ValueError("E_IDENTITY_LINK")
    current = client.request("GET", "/v1/auth/me")
    if (
        current.get("id") != user.get("id")
        or client.request("GET", "/v1/auth/central/status").get("linked") is not True
    ):
        raise ValueError("E_IDENTITY_LINK")
    return current


def select_current_space(client, user, messages):
    space = client.request("GET", "/v1/space")
    identity = str(uuid.UUID(space["id"]))
    if space.get("type") not in {"HOME", "BUSINESS"} or space.get("status") != "ACTIVE":
        raise ValueError("E_SPACE_UNAVAILABLE")
    print(messages["spaceAuthorized"])
    print(
        json.dumps(
            {
                "id": identity,
                "name": space["name"],
                "type": space["type"],
                "roles": user.get("roles", []),
            },
            ensure_ascii=True,
        )
    )
    if input(messages["spaceUse"] + " [USE/CANCEL]: ").strip().upper() != "USE":
        raise ValueError("E_SPACE_CANCELLED")
    client.installation.state.update(
        ownerSetup="authenticated",
        centralIdentity="linked",
        selectedSpace={"id": identity, "type": space["type"]},
    )
    client.installation.save()


def linked_setup(client, messages):
    fresh = client.request("GET", "/v1/auth/setup/status").get("setupRequired") is True
    if (
        not fresh
        and input(messages["identityAccess"] + " [ONLINE/OFFLINE]: ").strip().upper()
        == "OFFLINE"
    ):
        username = input(messages["localUsername"] + ": ").strip()
        password = getpass.getpass(messages["localPassword"] + ": ")
        user = client.login_or_setup(username, password)
        if client.request("GET", "/v1/auth/central/status").get("linked") is not True:
            user = connect_local_account(client, messages, user, password)
        del password
    else:
        if client.request("GET", "/v1/auth/central/config").get("enabled") is not True:
            client.installation.state["centralIdentity"] = "provider-required"
            client.installation.save()
            raise ValueError("E_IDENTITY_NOT_CONFIGURED")
        try:
            with provider_proof(client, messages, fresh) as (token, secret, prefix):
                body = {"operationToken": token, "confirm": True}
                if fresh:
                    print(messages["linkedOfflineIdentity"])
                    print(messages["offlineIdentityPolicy"])
                    username = input(messages["localUsername"] + ": ").strip()
                    password = getpass.getpass(messages["localPassword"] + ": ")
                    if password != getpass.getpass(messages["repeatPassword"] + ": "):
                        raise ValueError("E_PASSWORD_MISMATCH")
                    kind = (
                        input(messages["spaceType"] + " [HOME/BUSINESS]: ")
                        .strip()
                        .upper()
                    )
                    name = input(messages["spaceName"] + ": ").strip()
                    if kind not in {"HOME", "BUSINESS"} or not 1 <= len(name) <= 120:
                        raise ValueError("E_SPACE_TYPE")
                    body["credentials"] = {
                        "username": username,
                        "password": password,
                        "spaceType": kind,
                        "spaceName": name,
                    }
                response = client.request(
                    "POST", prefix + "/complete", body, bootstrap=secret
                )
                if fresh:
                    del password
                user = adopt_session(client, response)
        except ValueError as error:
            if fresh or getattr(error, "code", None) != "SPACE_ACCESS_REQUIRED":
                raise
            user = resolve_existing_access(client, messages)
    select_current_space(client, user, messages)
    return user
