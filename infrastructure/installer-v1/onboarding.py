"""Guided calls to existing Core APIs. Secrets stay in process memory/stdin."""

from __future__ import annotations

import getpass
import json
import os
import re
import subprocess
import uuid
from urllib.parse import urlsplit

from host import reject_links
from runtime import Installation

ROUTES = {
    ("GET", "/v1/auth/setup/status"),
    ("POST", "/v1/auth/setup"),
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/auth/logout"),
    ("GET", "/v1/auth/me"),
    ("GET", "/v1/space"),
    ("GET", "/v1/auth/central/config"),
    ("GET", "/v1/auth/central/status"),
    ("POST", "/v1/auth/central/start"),
    ("POST", "/v1/auth/central/poll"),
    ("POST", "/v1/auth/central/complete"),
    ("POST", "/v1/auth/central/cancel"),
    ("GET", "/v1/integrations/home-assistant"),
    ("POST", "/v1/integrations/home-assistant/probe"),
    ("POST", "/v1/integrations/home-assistant/connect"),
    ("GET", "/v1/devices"),
}


class CoreError(ValueError):
    pass


class CoreClient:
    def __init__(self, installation: Installation):
        self.installation = installation
        self.session: str | None = None

    def request(
        self,
        method: str,
        route: str,
        body: dict | None = None,
        bootstrap: str | None = None,
    ):
        if (method, route) not in ROUTES:
            raise ValueError("E_API_ROUTE: unsupported installer operation")
        config = [
            "silent",
            "show-error",
            "max-time = 30",
            'noproxy = "*"',
            "url = " + json.dumps("http://127.0.0.1:8080" + route),
            "request = " + json.dumps(method),
            'write-out = "\\n%{http_code}"',
        ]
        headers = ["Content-Type: application/json"]
        for value, prefix in (
            (self.session, "Authorization: Bearer "),
            (bootstrap, "X-Kyrion-Setup-Secret: "),
        ):
            if value is not None:
                if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", value):
                    raise ValueError("E_API: invalid credential shape")
                headers.append(prefix + value)
        config.extend("header = " + json.dumps(header) for header in headers)
        if body is not None:
            # curl's config parser unquotes once; the resulting value is JSON.
            config.append(
                "data-binary = " + json.dumps(json.dumps(body, ensure_ascii=True))
            )
        installation = self.installation
        arguments = [
            "docker",
            "compose",
            "--project-name",
            "kyrion-" + installation.state["installationId"],
            "--env-file",
            str(installation.target / ".env"),
            "-f",
            str(installation.target / "compose.yml"),
            "exec",
            "-T",
            "core",
            "curl",
            "--config",
            "-",
        ]
        try:
            result = subprocess.run(
                arguments,
                input="\n".join(config) + "\n",
                capture_output=True,
                text=True,
                timeout=40,
                check=False,
            )
            if result.returncode or len(result.stdout) > 2 * 1024 * 1024:
                raise ValueError("E_API: local Core unavailable")
            payload, status = result.stdout.rsplit("\n", 1)
            value = json.loads(payload) if payload else None
            if not 200 <= int(status) < 300:
                code = (
                    value.get("code", "E_API") if isinstance(value, dict) else "E_API"
                )
                raise ValueError(
                    code if re.fullmatch(r"[A-Z][A-Z_]{0,79}", code) else "E_API"
                )
            return value
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            raise ValueError("E_API: local Core unavailable") from None

    def login_or_setup(
        self,
        username: str,
        password: str,
        space_name: str | None = None,
        space_type: str = "HOME",
    ) -> dict:
        status = self.request("GET", "/v1/auth/setup/status")
        body = {"username": username, "password": password}
        if status.get("setupRequired") is True:
            if not space_name or not 1 <= len(space_name) <= 120:
                raise ValueError("E_SPACE: explicit Space name required")
            if space_type not in {"HOME", "BUSINESS"}:
                raise ValueError("E_SPACE_TYPE")
            body.update({"spaceType": space_type, "spaceName": space_name})
            bootstrap = (
                (self.installation.target / "secrets/bootstrap.secret")
                .read_text(encoding="utf-8")
                .strip()
            )
            response = self.request("POST", "/v1/auth/setup", body, bootstrap=bootstrap)
        else:
            response = self.request("POST", "/v1/auth/login", body)
        if not isinstance(response, dict) or not isinstance(
            response.get("sessionToken"), str
        ):
            raise CoreError("E_API: local authentication response invalid")
        self.session = response["sessionToken"]
        # Verify the real authenticated membership through the existing API.
        user = self.request("GET", "/v1/auth/me")
        self.installation.state["ownerSetup"] = "authenticated"
        self.installation.save()
        return user

    def connect_home_assistant(self, endpoint: str, token: str) -> dict:
        body = {"baseUrl": endpoint, "accessToken": token}
        probe = self.request("POST", "/v1/integrations/home-assistant/probe", body)
        if (
            not isinstance(probe, dict)
            or probe.get("reachable") is not True
            or probe.get("authenticated") is not True
        ):
            raise ValueError("E_HA_PROBE: no authenticated connection")
        result = self.request("POST", "/v1/integrations/home-assistant/connect", body)
        if not isinstance(result, dict) or result.get("connected") is not True:
            raise ValueError("E_HA_CONNECT: connection not confirmed")
        return result

    def close(self) -> None:
        if self.session:
            try:
                self.request("POST", "/v1/auth/logout")
            finally:
                self.session = None


def guided_setup(installation: Installation, messages: dict[str, str]) -> None:
    if input(messages["setupNow"] + " [YES]: ").strip() != "YES":
        return
    client = CoreClient(installation)
    try:
        status = client.request("GET", "/v1/auth/setup/status")
        space_name = (
            input(messages["spaceName"] + ": ").strip()
            if status.get("setupRequired") is True
            else None
        )
        space_type = (
            input(messages["spaceType"] + " [HOME/BUSINESS]: ").strip().upper()
            if space_name is not None
            else "HOME"
        )
        username = input(messages["localUsername"] + ": ").strip()
        password = getpass.getpass(messages["localPassword"] + ": ")
        if space_name is not None and password != getpass.getpass(
            messages["repeatPassword"] + ": "
        ):
            raise ValueError("E_PASSWORD_MISMATCH")
        user = client.login_or_setup(username, password, space_name, space_type)
        # Linking the same account uses Core's RFC8628 flow; the installer never
        # collects a website password, handles a provider token or grants a role.
        config = client.request("GET", "/v1/auth/central/config")
        if (
            config.get("enabled") is True
            and input(messages["linkNow"] + " [YES]: ").strip() == "YES"
        ):
            link_existing_identity(client, password, messages)
        else:
            print(messages["linkLater"])
        del password
        if (
            "OWNER" in user.get("roles", [])
            and input(messages["recoveryNow"] + " [RECOVERY]: ").strip() == "RECOVERY"
        ):
            space = client.request("GET", "/v1/space")
            provision_recovery(installation, str(uuid.UUID(space["id"])), messages)
        print(messages["hardwareHelp"])
        hardware = input(messages["hardwareChoice"] + ": ").strip().split(",")
        allowed = {"ha", "zigbee", "matter", "thread", "audio", "none"}
        selection = sorted(
            {
                entry.strip().lower()
                for entry in hardware
                if entry.strip().lower() in allowed
            }
        )
        if "none" in selection and len(selection) > 1:
            raise ValueError("E_HARDWARE_SELECTION")
        installation.state["hardwareSelection"] = selection
        installation.save()
        if "ha" in selection:
            current = client.request("GET", "/v1/integrations/home-assistant")
            if current.get("configured") is True:
                print(messages["haExisting"])
            else:
                print(messages["haScope"])
                if input(messages["haConsent"] + " [IMPORT]: ").strip() == "IMPORT":
                    endpoint = input(messages["haEndpoint"] + ": ").strip()
                    token = getpass.getpass(messages["haToken"] + ": ")
                    result = client.connect_home_assistant(endpoint, token)
                    del token
                    print(
                        messages["haImported"]
                        + ": "
                        + str(result["importedDeviceCount"])
                    )
        print(messages["tutorial"])
        installation.state["tutorial"] = "offered"
        installation.save()
    finally:
        client.close()


def provision_recovery(
    installation: Installation, space_id: str, messages: dict[str, str]
) -> None:
    if os.name != "posix" or os.geteuid() != 0:
        raise ValueError("E_PLATFORM")
    space_id = str(uuid.UUID(space_id))
    directory = installation.target / "recovery"
    reject_links(directory)
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    os.chown(directory, 10001, 10001)
    key = directory / (space_id + ".host-key")
    if key.exists() or key.is_symlink():
        raise ValueError("E_RECOVERY_EXISTING: existing recovery is never overwritten")
    print(messages["recoveryConsole"])
    installation.compose("stop", "--timeout", "30", "web", "core")
    try:
        command = [
            "docker",
            "compose",
            "--project-name",
            "kyrion-" + installation.state["installationId"],
            "--env-file",
            str(installation.target / ".env"),
            "-f",
            str(installation.target / "compose.yml"),
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "java",
            "--volume",
            str(directory) + ":/run/kyrion-recovery",
            "core",
            "-Dloader.main=dev.kyrion.core.security.LocalSecurityAdmin",
            "-cp",
            "/opt/kyrion/app.jar",
            "org.springframework.boot.loader.launch.PropertiesLauncher",
            "provision",
            space_id,
            "/run/kyrion-recovery/" + space_id + ".host-key",
        ]
        # Inherit the real terminal. The existing host-only tool refuses pipes,
        # verifies OWNER password and audit integrity, and shows a code once.
        result = subprocess.run(command, check=False)
        if (
            result.returncode
            or not key.is_file()
            or key.stat().st_mode & 0o077
            or key.stat().st_uid != 10001
        ):
            raise ValueError("E_RECOVERY_NOT_PROVISIONED")
        installation.state["recovery"] = "provisioned-by-core-host-tool"
        installation.save()
    finally:
        installation.compose("start", "core", "web")


def link_existing_identity(
    client: CoreClient, password: str, messages: dict[str, str]
) -> None:
    if client.request("GET", "/v1/auth/central/status").get("linked") is True:
        print(messages["alreadyLinked"])
        return
    operation = client.request(
        "POST", "/v1/auth/central/start", {"mode": "LINK", "currentPassword": password}
    )
    token = operation["operationToken"]
    completed = False
    try:
        uri = operation["verificationUri"]
        if (
            urlsplit(uri).scheme != "https"
            or urlsplit(uri).username
            or urlsplit(uri).fragment
        ):
            raise ValueError("E_IDENTITY_URI: trusted HTTPS provider required")
        print(messages["centralBrowser"])
        print(uri)
        print(messages["centralCode"] + ": " + operation["userCode"])
        # The user returns after authenticating in their normal browser. Core
        # enforces expiry, poll pacing, session binding and single use.
        for _ in range(20):
            if input(messages["centralCheck"] + " [CHECK/skip]: ").strip() != "CHECK":
                return
            status = client.request(
                "POST", "/v1/auth/central/poll", {"operationToken": token}
            )
            if status.get("status") == "CONFIRM":
                if input(messages["centralConfirm"] + " [LINK]: ").strip() == "LINK":
                    result = client.request(
                        "POST",
                        "/v1/auth/central/complete",
                        {"operationToken": token, "confirm": True},
                    )
                    completed = result.get("linked") is True
                    if not completed:
                        raise ValueError("E_IDENTITY_LINK")
                    client.installation.state["centralIdentity"] = "linked"
                    client.installation.save()
                return
            print(messages["centralPending"])
    finally:
        if not completed:
            client.request("POST", "/v1/auth/central/cancel", {"operationToken": token})
