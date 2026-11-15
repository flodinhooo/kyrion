"""Journaled, reviewed extension of exact owned Linux agent proxy definitions."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from authority import require_active
from bundle import sha256
from host import reject_links
from linux_startup import machine_binding
from node_pairing import configured_origin
from node_transport import agent_handle

KEY = "agentIngressTransition"
FILE = "data/Caddyfile"
PHASES = {
    "prepared",
    "stopped",
    "published",
    "started",
    "verified",
    "recovering",
    "restored",
    "recovered",
}


def now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def definitions(installation) -> tuple[str, set[str]]:
    hostname = installation.configuration["hostname"]
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", hostname):
        raise ValueError("E_AGENT_INGRESS_CUSTOM")
    current = (
        (Path(__file__).parent / "templates/Caddyfile")
        .read_text(encoding="utf-8")
        .replace("__KYRION_HOSTNAME__", hostname)
        .replace("__KYRION_AGENT_HANDLE__", agent_handle("core:8080"))
    )
    legacy = (
        "https://" + hostname + " {\n"
        "  tls /etc/caddy/tls/cert.pem /etc/caddy/tls/key.pem\n"
        "  reverse_proxy web:3000\n}\n"
    )
    return current, {current, legacy, current.replace(" /v1/gateway-agent/tasks", "")}


def transition(installation) -> dict | None:
    value = installation.state.get(KEY)
    if value is None:
        return None
    fields = {
        "formatVersion",
        "id",
        "phase",
        "before",
        "after",
        "beforeSha256",
        "afterSha256",
        "actorId",
        "lastActorId",
        "spaceId",
        "machine",
        "preparedAt",
        "updatedAt",
        "lastError",
        "recoveredBy",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or value.get("phase") not in PHASES
    ):
        raise ValueError("E_AGENT_INGRESS_JOURNAL")
    for key in ("id", "actorId", "lastActorId", "spaceId"):
        if not isinstance(value[key], str) or str(uuid.UUID(value[key])) != value[key]:
            raise ValueError("E_AGENT_INGRESS_JOURNAL")
    _, known = definitions(installation)
    for name in ("before", "after"):
        if (
            not isinstance(value[name], str)
            or value[name] not in known
            or digest(value[name]) != value[name + "Sha256"]
        ):
            raise ValueError("E_AGENT_INGRESS_JOURNAL")
    if value["machine"] != machine_binding(installation.state["installationId"]):
        raise ValueError("E_STARTUP_HOST_CHANGED")
    if value["recoveredBy"] not in {None, "os-root"} or (
        value["lastError"] is not None
        and (
            not isinstance(value["lastError"], str)
            or not re.fullmatch(r"E_[A-Z_]{1,77}", value["lastError"])
        )
    ):
        raise ValueError("E_AGENT_INGRESS_JOURNAL")
    for name in ("preparedAt", "updatedAt"):
        if (
            not isinstance(value[name], str)
            or datetime.datetime.fromisoformat(value[name]).tzinfo is None
        ):
            raise ValueError("E_AGENT_INGRESS_JOURNAL")
    return value


def inspect(installation) -> str | None:
    if os.name != "posix" or installation.state.get("backend") == "windows-native":
        raise ValueError("E_AGENT_INGRESS_PLATFORM")
    files = installation.state["files"]
    if FILE not in files:
        raise ValueError("E_AGENT_INGRESS_CUSTOM")
    # Only this transaction's exact public configuration may temporarily differ
    # from the committed file digest after a crash between replace and save.
    installation.state["files"] = {
        name: value for name, value in files.items() if name != FILE
    }
    try:
        installation.verify_files()
    finally:
        installation.state["files"] = files
    path = installation.target / FILE
    reject_links(path)
    for directory in (path.parent, installation.target):
        if directory.stat().st_uid != 0 or directory.stat().st_mode & 0o022:
            raise ValueError("E_AGENT_INGRESS_OWNERSHIP")
    value = transition(installation)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if value is not None and value["phase"] not in {"verified", "recovered"}:
            return None
        raise ValueError("E_AGENT_INGRESS_CUSTOM") from None
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_mode & 0o077
            or metadata.st_nlink != 1
        ):
            raise ValueError("E_AGENT_INGRESS_OWNERSHIP")
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError("E_AGENT_INGRESS_CUSTOM")
    text = raw.decode("utf-8")
    allowed = (
        {files[FILE]}
        if value is None or value["phase"] in {"verified", "recovered"}
        else {value["beforeSha256"], value["afterSha256"]}
    )
    if digest(text) not in allowed or text not in definitions(installation)[1]:
        raise ValueError("E_AGENT_INGRESS_CUSTOM")
    return text


def actor(client) -> dict:
    value = client.request("GET", "/v1/auth/me")
    if (
        not isinstance(value, dict)
        or value.get("enabled") is not True
        or not isinstance(value.get("permissions"), list)
        or not all(isinstance(item, str) for item in value["permissions"])
        or not {"system_settings:update", "gateways:create"}.issubset(
            value["permissions"]
        )
    ):
        raise ValueError("E_AGENT_INGRESS_PERMISSION")
    space = client.request("GET", "/v1/space")
    if not isinstance(space, dict) or space.get("status") != "ACTIVE":
        raise ValueError("E_SPACE_UNAVAILABLE")
    try:
        user_id, space_id = str(uuid.UUID(value["id"])), str(uuid.UUID(space["id"]))
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise ValueError("E_AGENT_INGRESS_PERMISSION") from error
    capability = client.request("GET", "/v1/gateway-agent/enrollment-capabilities")
    if (
        not isinstance(capability, dict)
        or type(capability.get("enrollmentProtocol")) is not int
        or capability["enrollmentProtocol"] != 2
        or capability.get("clientCredential") is not True
        or type(capability.get("formatVersion")) is not int
        or capability["formatVersion"] != 1
        or capability.get("acknowledgementWithinOriginalExpiry") is not True
        or type(capability.get("taskPolicyVersion")) is not int
        or capability["taskPolicyVersion"] != 1
    ):
        raise ValueError("E_AGENT_ENROLLMENT_UPGRADE_REQUIRED")
    return {"actorId": user_id, "spaceId": space_id}


def publish(installation, text: str) -> None:
    path = installation.target / FILE
    inspect(installation)
    temporary = path.with_name(".Caddyfile.ingress-" + secrets.token_hex(12))
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(text.encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        installation.state["files"][FILE] = digest(text)
    finally:
        temporary.unlink(missing_ok=True)


class ComposeRuntime:
    def __init__(self, installation):
        from update_compose import Compose

        if os.geteuid() != 0 or installation.state.get("runtimeImageIds") is None:
            raise ValueError("E_AGENT_INGRESS_OWNERSHIP")
        self.installation = installation
        require_workers(installation)
        self.adapter = Compose(installation)
        if installation.state.get("startupPolicy") is not None:
            from linux_startup import validate_runtime

            validate_runtime(installation)

    def validate(self, text: str) -> None:
        self.adapter.compose(
            "exec",
            "-T",
            "caddy",
            "caddy",
            "validate",
            "--config",
            "-",
            "--adapter",
            "caddyfile",
            payload=text.encode(),
            timeout=45,
        )

    def stop(self) -> None:
        self.adapter.compose("stop", "--timeout", "30", "caddy", timeout=60)

    def start(self) -> None:
        self.adapter.compose(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--pull",
            "never",
            "caddy",
            timeout=120,
        )

    def probe(self) -> None:
        from node_entry import component

        component(require_linux=False)
        from kyrion_gateway_agent.client import CoreRequestError, prepared_capabilities

        origin, certificate = configured_origin(self.installation)
        for attempt in range(4):
            try:
                prepared_capabilities(origin, str(certificate), sha256(certificate))
                return
            except CoreRequestError as error:
                if (
                    attempt == 3
                    or error.status in {400, 401, 403, 404, 405}
                    or str(error)
                    in {
                        "E_AGENT_TLS_CONFIGURATION",
                        "E_AGENT_TLS_REQUIRED",
                        "E_AGENT_ENROLLMENT_UPGRADE_REQUIRED",
                    }
                ):
                    raise
                time.sleep(2)

    def probe_original(self) -> None:
        from node_entry import component

        component(require_linux=False)
        from kyrion_gateway_agent.client import trusted_context
        from kyrion_gateway_agent.lan_transport import connect_local

        origin, certificate = configured_origin(self.installation)
        parsed = urlsplit(origin)
        context = trusted_context(str(certificate), sha256(certificate))
        if not parsed.hostname:
            raise ValueError("E_AGENT_INGRESS_VERIFY")
        with (
            connect_local(parsed.hostname, parsed.port or 443, 5) as connection,
            context.wrap_socket(connection, server_hostname=parsed.hostname),
        ):
            pass  # Verified TLS listener only; no claim of Core/web readiness.


def require_workers(installation) -> None:
    """Source changes do not upgrade already installed background executables."""
    checked = set()
    for field in ("startupPolicy", "updatePolicy", "backupPolicy"):
        policy = installation.state.get(field)
        if policy is None:
            continue
        if not isinstance(policy, dict) or type(policy.get("enabled")) is not bool:
            raise ValueError("E_AGENT_INGRESS_WORKER")
        if not policy["enabled"]:
            continue
        name = policy.get("workerFile")
        if not isinstance(name, str) or not re.fullmatch(
            r"maintenance-[a-f0-9]{32}", name
        ):
            raise ValueError("E_AGENT_INGRESS_WORKER")
        if name in checked:
            continue
        checked.add(name)
        path = installation.target / name
        reject_links(path)
        expected = installation.state["files"].get(name)
        if (
            not isinstance(expected, str)
            or sha256(path) != expected
            or path.stat().st_uid != 0
            or path.stat().st_mode & 0o077
        ):
            raise ValueError("E_AGENT_INGRESS_WORKER")
        result = subprocess.run(
            [str(path), "--capabilities"],
            cwd=installation.target,
            env={"PATH": "/usr/bin:/bin", "LANG": "C"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode or len(result.stdout) > 16384:
            raise ValueError("E_AGENT_INGRESS_WORKER")
        try:
            capability = json.loads(result.stdout)
        except (ValueError, UnicodeError) as error:
            raise ValueError("E_AGENT_INGRESS_WORKER") from error
        if (
            not isinstance(capability, dict)
            or type(capability.get("formatVersion")) is not int
            or capability["formatVersion"] != 1
            or capability.get("agentIngressFence") is not True
        ):
            raise ValueError("E_AGENT_INGRESS_WORKER")


def checkpoint(installation, phase: str) -> None:
    value = transition(installation)
    if value is None:
        raise ValueError("E_AGENT_INGRESS_JOURNAL")
    value["phase"], value["updatedAt"], value["lastError"] = phase, now(), None
    installation.state["formatVersion"] = 1 if phase in {"verified", "recovered"} else 2
    installation.save()


def apply(installation, approval: dict | None, action: str, *, runtime=None) -> dict:
    if action not in {"configure", "resume", "recover", "status"}:
        raise ValueError("E_AGENT_INGRESS_ACTION")
    require_active(installation.state, ingress=True)
    before = inspect(installation)
    current, _ = definitions(installation)
    value = transition(installation)
    if action == "status":
        return {
            "pending": value is not None
            and value["phase"] not in {"verified", "recovered"},
            "phase": value["phase"] if value else "not-configured",
            "currentConnectionChecked": False,
            "configurationMissing": before is None,
            "managedAgentRoutesPresent": before == current,
        }
    if os.geteuid() != 0:
        raise ValueError("E_AGENT_INGRESS_OWNERSHIP")
    runtime = runtime if runtime is not None else ComposeRuntime(installation)
    if action == "recover":
        if value is None or value["phase"] == "verified":
            raise ValueError("E_AGENT_INGRESS_RECOVERY")
        if value["phase"] == "recovered":
            runtime.probe_original()
            return {
                "phase": "recovered",
                "originalProxyTlsVerified": True,
                "coreVerified": False,
            }
        value["recoveredBy"] = "os-root"
        checkpoint(installation, "recovering")
    else:
        if (
            not isinstance(approval, dict)
            or set(approval) != {"actorId", "spaceId"}
            or any(str(uuid.UUID(approval[key])) != approval[key] for key in approval)
        ):
            raise ValueError("E_AGENT_INGRESS_PERMISSION")
        if value is not None and value["phase"] in {"recovering", "restored"}:
            raise ValueError("E_AGENT_INGRESS_RECOVERY")
        if value is None or value["phase"] in {"verified", "recovered"}:
            if before == current:
                runtime.probe()
                return {
                    "phase": "verified",
                    "agentConnectionVerified": True,
                    "changed": False,
                }
            if action == "resume":
                raise ValueError("E_AGENT_INGRESS_JOURNAL")
            runtime.validate(current)
            value = {
                "formatVersion": 1,
                "id": str(uuid.uuid4()),
                "phase": "prepared",
                "before": before,
                "after": current,
                "beforeSha256": digest(before),
                "afterSha256": digest(current),
                **approval,
                "lastActorId": approval["actorId"],
                "machine": machine_binding(installation.state["installationId"]),
                "preparedAt": now(),
                "updatedAt": now(),
                "lastError": None,
                "recoveredBy": None,
            }
            installation.state[KEY] = value
            # Older installers must refuse an unfinished operation even if they
            # predate the optional ingress fence field entirely.
            installation.state["formatVersion"] = 2
            installation.save()
        elif value["spaceId"] != approval["spaceId"]:
            raise ValueError("E_AGENT_INGRESS_PERMISSION")
        else:
            value["lastActorId"] = approval["actorId"]
            installation.save()
        if value["phase"] in {"published", "started"} and before != value["after"]:
            runtime.stop()
            checkpoint(installation, "stopped")
    try:
        if value["phase"] == "prepared":
            runtime.stop()
            checkpoint(installation, "stopped")
        if value["phase"] == "stopped":
            publish(installation, value["after"])
            checkpoint(installation, "published")
        if value["phase"] == "published":
            runtime.start()
            checkpoint(installation, "started")
        if value["phase"] == "started":
            runtime.probe()
            checkpoint(installation, "verified")
        if value["phase"] == "recovering":
            runtime.stop()
            publish(installation, value["before"])
            checkpoint(installation, "restored")
        if value["phase"] == "restored":
            runtime.start()
            runtime.probe_original()
            checkpoint(installation, "recovered")
    except Exception as error:
        code = str(error).split(":", 1)[0]
        value["lastError"] = (
            code if re.fullmatch(r"E_[A-Z_]{1,77}", code) else "E_AGENT_INGRESS_RUNTIME"
        )
        value["updatedAt"] = now()
        installation.save()
        raise
    return {
        "phase": value["phase"],
        "agentConnectionVerified": value["phase"] == "verified",
        "originalProxyTlsVerified": value["phase"] == "recovered",
        "changed": True,
    }


def guided(client, installation, messages, action: str) -> dict | None:
    approval = actor(client) if action in {"configure", "resume"} else None
    current = inspect(installation)
    desired, _ = definitions(installation)
    origin, _ = configured_origin(installation)
    print(messages["agentIngressScope"])
    print(
        json.dumps(
            {
                "origin": origin,
                "operation": action,
                "localPeersOnly": True,
                "restart": "owned-proxy-only",
                "newPorts": False,
                "downloads": False,
                "configurationChanges": current != desired,
            },
            ensure_ascii=True,
        )
    )
    if action != "status":
        confirmation = (
            "RESTORE-AGENT-INGRESS" if action == "recover" else "ENABLE-AGENT-INGRESS"
        )
        if (
            input(
                messages["agentIngressReview"] + " [" + confirmation + "/CANCEL]: "
            ).strip()
            != confirmation
        ):
            return None
    result = apply(installation, approval, action)
    print(json.dumps(result, ensure_ascii=True))
    return result
