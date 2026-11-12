"""Guided calls to existing Core APIs. Secrets stay in process memory/stdin."""

from __future__ import annotations

import getpass
import json
import os
import re
import subprocess
import uuid
from urllib.parse import urlsplit

from host import inventory, reject_links
from models import guided_recommendation
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
    ("POST", "/v1/auth/central/setup/start"),
    ("POST", "/v1/auth/central/setup/poll"),
    ("POST", "/v1/auth/central/setup/complete"),
    ("POST", "/v1/auth/central/setup/cancel"),
    ("GET", "/v1/integrations/home-assistant"),
    ("POST", "/v1/integrations/home-assistant/probe"),
    ("POST", "/v1/integrations/home-assistant/connect"),
    ("POST", "/v1/integrations/home-assistant/sync"),
    ("GET", "/v1/integrations/home-assistant/preview"),
    ("POST", "/v1/integrations/home-assistant/preview"),
    ("GET", "/v1/integrations/home-assistant/selection"),
    ("POST", "/v1/integrations/home-assistant/selection"),
    ("GET", "/v1/home/rooms"),
    ("POST", "/v1/device-commands"),
    ("GET", "/v1/devices"),
}


class CoreError(ValueError):
    def __init__(self, code: str, status: int | None = None):
        self.code = (
            code if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", code) else "E_API"
        )
        self.status = status
        super().__init__(
            self.code
            if self.code == self.code.upper()
            else "E_CORE_" + self.code.upper()
        )


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
        if self.installation.state.get("backend") == "windows-native":
            return self._native_request(method, route, body, bootstrap)
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
                raise CoreError(code if isinstance(code, str) else "E_API", int(status))
            return value
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            raise ValueError("E_API: local Core unavailable") from None

    def _native_request(self, method, route, body, bootstrap):
        import ssl
        import urllib.error
        import urllib.request

        from native_roles import read_configuration

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, _request, _fp, _code, _message, _headers, _url):
                return None

        config = read_configuration(self.installation.target)
        headers = {"Content-Type": "application/json"}
        for credential, name, prefix in (
            (self.session, "Authorization", "Bearer "),
            (bootstrap, "X-Kyrion-Setup-Secret", ""),
        ):
            if credential is not None:
                if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", credential):
                    raise ValueError("E_API_CREDENTIAL")
                headers[name] = prefix + credential
        request = urllib.request.Request(
            "https://127.0.0.1:" + str(config["ports"]["core"]) + route,
            data=json.dumps(body, ensure_ascii=True).encode()
            if body is not None
            else None,
            headers=headers,
            method=method,
        )
        try:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                NoRedirect(),
                urllib.request.HTTPSHandler(
                    context=ssl.create_default_context(
                        cafile=str(self.installation.target / "core-cert.pem")
                    )
                ),
            )
            try:
                response = opener.open(request, timeout=30)
            except urllib.error.HTTPError as response_error:
                response = response_error
            with response:
                data = response.read(2 * 1024**2 + 1)
                status = response.status
            if len(data) > 2 * 1024**2:
                raise ValueError("E_API_RESPONSE_SIZE")
            value = json.loads(data) if data else None
            if not 200 <= status < 300:
                code = (
                    value.get("code", "E_API") if isinstance(value, dict) else "E_API"
                )
                raise CoreError(code if isinstance(code, str) else "E_API", status)
            return value
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
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
        from linked_onboarding import linked_setup

        user = linked_setup(client, messages)
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
        if any(
            entry.strip().lower() not in allowed for entry in hardware if entry.strip()
        ):
            raise ValueError("E_HARDWARE_SELECTION")
        if "none" in selection and len(selection) > 1:
            raise ValueError("E_HARDWARE_SELECTION")
        installation.state["hardwareSelection"] = selection
        installation.save()
        if "ha" in selection:
            guided_home_assistant(client, messages)
        from model_cache import cached_catalog

        recommendation = guided_recommendation(
            inventory(installation.target),
            messages,
            lambda: cached_catalog(installation),
        )
        if recommendation is not None:
            installation.state["aiRecommendation"] = recommendation
            installation.save()
        print(messages["tutorial"])
        installation.state["tutorial"] = "offered"
        installation.save()
    finally:
        client.close()


def selected_indices(value: str, count: int) -> list[int]:
    value = value.strip().lower()
    if value in {"all", "alle"}:
        return list(range(count))
    if value in {"none", "keine"}:
        return []
    parts = value.split(",")
    if not parts or any(not part.strip().isdigit() for part in parts):
        raise ValueError("E_SELECTION")
    selected = [int(part.strip()) - 1 for part in parts]
    if len(set(selected)) != len(selected) or any(
        index < 0 or index >= count for index in selected
    ):
        raise ValueError("E_SELECTION")
    return selected


def guided_home_assistant(client: CoreClient, messages: dict[str, str]) -> None:
    if input(messages["haConfigure"] + " [CONFIGURE/skip]: ").strip() != "CONFIGURE":
        return
    current = client.request("GET", "/v1/integrations/home-assistant")
    body = {}
    if current.get("configured") is True:
        preview = client.request("GET", "/v1/integrations/home-assistant/preview")
    else:
        body = {
            "baseUrl": input(messages["haEndpoint"] + ": ").strip(),
            "accessToken": getpass.getpass(messages["haToken"] + ": "),
        }
        preview = client.request(
            "POST", "/v1/integrations/home-assistant/preview", body
        )
    devices = preview.get("devices")
    if not isinstance(devices, list) or type(preview.get("revision")) is not int:
        raise CoreError("E_HA_PREVIEW")
    print(messages["haSelectScope"])
    for index, device in enumerate(devices, 1):
        print(
            json.dumps(
                {
                    "number": index,
                    "name": device["name"],
                    "sourceRoom": device.get("sourceRoom"),
                },
                ensure_ascii=True,
            )
        )
    chosen = selected_indices(input(messages["haChooseDevices"] + ": "), len(devices))
    rooms = client.request("GET", "/v1/home/rooms")
    if not isinstance(rooms, list):
        raise CoreError("E_HA_ROOMS")
    choices = []
    for index in chosen:
        device = devices[index]
        print(json.dumps({"device": device["name"]}, ensure_ascii=True))
        for number, entity in enumerate(device["entities"], 1):
            print(
                json.dumps(
                    {
                        "number": number,
                        "name": entity["name"],
                        "state": entity["state"],
                        "supportsPower": entity["supportsPower"],
                    },
                    ensure_ascii=True,
                )
            )
        entities = [
            device["entities"][number]
            for number in selected_indices(
                input(messages["haChooseEntities"] + ": "), len(device["entities"])
            )
        ]
        if not entities:
            raise ValueError("E_HA_ENTITY_SELECTION")
        allow = False
        if sum(entity["supportsPower"] is True for entity in entities) == 1:
            allow = (
                input(messages["haControlConsent"] + " [ALLOW/skip]: ").strip()
                == "ALLOW"
            )
        else:
            print(messages["haControlSingle"])
        for number, room in enumerate(rooms, 1):
            print(
                json.dumps({"number": number, "room": room["name"]}, ensure_ascii=True)
            )
        room_choice = (
            input(messages["haChooseRoom"] + " [auto/none/number]: ").strip().lower()
        )
        override, room_id = room_choice not in {"auto", ""}, None
        if override and room_choice not in {"none", "keine"}:
            indices = selected_indices(room_choice, len(rooms))
            if len(indices) != 1:
                raise ValueError("E_HA_ROOM_SELECTION")
            room_id = rooms[indices[0]]["id"]
        choices.append(
            {
                "key": device["key"],
                "entityKeys": [entity["key"] for entity in entities],
                "allowControl": allow,
                "overrideRoom": override,
                "roomId": room_id,
            }
        )
    print(messages["haSelectionReview"].format(count=len(choices)))
    if input("[APPLY/skip]: ").strip() != "APPLY":
        return
    result = client.request(
        "POST",
        "/v1/integrations/home-assistant/selection",
        {**body, "expectedRevision": preview["revision"], "devices": choices},
    )
    body.clear()
    if result.get("reason") is not None or type(result.get("imported")) is not int:
        raise CoreError("E_HA_SYNC")
    client.installation.state["homeAssistant"] = "selected-and-imported"
    client.installation.save()
    print(messages["haImported"] + ": " + str(result["imported"]))
    if (
        any(choice["allowControl"] for choice in choices)
        and input(messages["haFirstAction"] + " [TEST/skip]: ").strip() == "TEST"
    ):
        catalog = client.request("GET", "/v1/devices")
        if not isinstance(catalog, list):
            raise CoreError("E_HA_CATALOG")
        candidates = [
            device
            for device in catalog
            if device.get("provider") == "home_assistant"
            and device.get("availability") == "online"
            and any(
                capability.get("id") == "power.set"
                for capability in device.get("capabilities", [])
            )
        ]
        for number, device in enumerate(candidates, 1):
            print(
                json.dumps(
                    {"number": number, "device": device["displayName"]},
                    ensure_ascii=True,
                )
            )
        selected = selected_indices(
            input(messages["haChooseActionDevice"] + ": "), len(candidates)
        )
        if len(selected) != 1:
            raise ValueError("E_HA_ACTION_SELECTION")
        device = candidates[selected[0]]
        action = input(
            messages["haActionConfirm"] + " [TURN-ON/TURN-OFF/skip]: "
        ).strip()
        if action not in {"TURN-ON", "TURN-OFF"}:
            return
        result = client.request(
            "POST",
            "/v1/device-commands",
            {
                "capability": "power.set",
                "selector": {"provider": "home_assistant", "deviceId": device["id"]},
                "arguments": {"on": action == "TURN-ON"},
            },
        )
        print(
            json.dumps(
                {
                    "requested": result.get("requested"),
                    "succeeded": result.get("succeeded"),
                    "failed": result.get("failed"),
                }
            )
        )


def provision_recovery(
    installation: Installation, space_id: str, messages: dict[str, str]
) -> None:
    if installation.state.get("backend") == "windows-native":
        from native_recovery import provision_owner_recovery

        print(messages["recoveryConsole"])
        provision_owner_recovery(installation, space_id)
        return
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
