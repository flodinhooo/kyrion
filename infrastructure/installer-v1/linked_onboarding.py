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
def provider_proof(client, messages, fresh: bool):
    secret = (
        (client.installation.target / "secrets/bootstrap.secret").read_text().strip()
        if fresh
        else None
    )
    prefix = "/v1/auth/central/setup" if fresh else "/v1/auth/central"
    operation = client.request(
        "POST",
        prefix + "/start",
        None if fresh else {"mode": "LOGIN"},
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
        if (
            not 0 < remaining <= 601
            or type(interval) is not int
            or not 1 <= interval <= 60
        ):
            raise ValueError("E_IDENTITY_OPERATION")
        print(messages["centralBrowser"])
        print(uri)
        print(messages["centralCode"] + ": " + operation["userCode"])
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
        del password
        if client.request("GET", "/v1/auth/central/status").get("linked") is not True:
            raise ValueError("E_IDENTITY_LINK_REQUIRED")
    else:
        if client.request("GET", "/v1/auth/central/config").get("enabled") is not True:
            client.installation.state["centralIdentity"] = "provider-required"
            client.installation.save()
            raise ValueError("E_IDENTITY_NOT_CONFIGURED")
        with provider_proof(client, messages, fresh) as (token, secret, prefix):
            body = {"operationToken": token, "confirm": True}
            if fresh:
                print(messages["linkedOfflineIdentity"])
                username = input(messages["localUsername"] + ": ").strip()
                password = getpass.getpass(messages["localPassword"] + ": ")
                if password != getpass.getpass(messages["repeatPassword"] + ": "):
                    raise ValueError("E_PASSWORD_MISMATCH")
                kind = (
                    input(messages["spaceType"] + " [HOME/BUSINESS]: ").strip().upper()
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
    select_current_space(client, user, messages)
    return user
