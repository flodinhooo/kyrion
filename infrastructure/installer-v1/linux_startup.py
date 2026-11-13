"""Owned Linux boot supervision using the existing frozen installer and journal."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from authority import require_active
from bundle import sha256, unique_object
from host import reject_links
from recovery import load_installation
from runtime import installation_lock
from update_schedule import publish_unit, systemctl
from update_worker import validate_host

OVERLAY = "compose-startup.yml"
OVERLAY_TEXT = "services:\n" + "".join(
    "  " + role + ':\n    restart: "on-failure:5"\n'
    for role in ("postgres", "core", "web", "caddy")
)


def require_root() -> None:
    if os.name != "posix" or os.geteuid() != 0:
        raise ValueError("E_PLATFORM")


def machine_binding(identifier: str) -> str:
    raw = Path("/etc/machine-id").read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{32}", raw) or raw == "0" * 32:
        raise ValueError("E_STARTUP_HOST_ID")
    return hashlib.sha256(
        ("kyrion-host-v1:" + str(uuid.UUID(identifier)) + ":" + raw).encode()
    ).hexdigest()


def policy(installation) -> dict | None:
    value = installation.state.get("startupPolicy")
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "formatVersion",
            "enabled",
            "workerFile",
            "workerSha256",
            "unitSha256",
            "state",
            "machine",
            "daemon",
        }
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or type(value.get("enabled")) is not bool
        or value.get("state")
        not in {"registering", "registered", "disabled", "removed"}
        or any(
            not isinstance(value.get(key), str)
            or not re.fullmatch(r"[a-f0-9]{64}", value[key])
            for key in ("workerSha256", "unitSha256", "machine")
        )
        or value.get("workerFile") != "maintenance-" + value["workerSha256"][:32]
        or not isinstance(value.get("daemon"), dict)
        or set(value["daemon"]) != {"id", "sockets"}
        or not isinstance(value["daemon"].get("id"), str)
        or not re.fullmatch(r"[A-Za-z0-9:._-]{8,128}", value["daemon"]["id"])
        or not isinstance(value["daemon"].get("sockets"), list)
        or not value["daemon"]["sockets"]
        or any(
            not isinstance(item, str) or not item.startswith("/")
            for item in value["daemon"]["sockets"]
        )
    ):
        raise ValueError("E_STARTUP_POLICY")
    return value


def require_bound(installation) -> None:
    value = policy(installation)
    if value is not None and value["machine"] != machine_binding(
        installation.state["installationId"]
    ):
        raise ValueError("E_STARTUP_HOST_CHANGED")


def validate_runtime(installation):
    require_bound(installation)
    from update_compose import Compose

    adapter = Compose(installation)
    value = policy(installation)
    if value is not None and value["daemon"] != adapter.daemon:
        raise ValueError("E_STARTUP_DOCKER_CHANGED")
    return adapter


def unit_name(installation) -> str:
    return (
        "kyrion-"
        + str(uuid.UUID(installation.state["installationId"]))
        + "-platform.service"
    )


def definition(installation, worker: str) -> str:
    target = str(installation.target)
    if not re.fullmatch(r"/[A-Za-z0-9/_-]+", target) or not re.fullmatch(
        r"maintenance-[a-f0-9]{32}", worker
    ):
        raise ValueError("E_STARTUP_POLICY")
    return (
        "[Unit]\nDescription=Kyrion ordered platform startup\n"
        "After=docker.service network-online.target\nRequires=docker.service\n"
        "Wants=network-online.target\nStartLimitIntervalSec=infinity\nStartLimitBurst=3\n"
        "\n[Service]\nType=oneshot\nRemainAfterExit=yes\nUser=root\nUMask=0077\n"
        "WorkingDirectory="
        + target
        + "\nExecStart="
        + target
        + "/"
        + worker
        + " --background-platform-start --target "
        + target
        + "\nTimeoutStartSec=5min\nRestart=on-failure\nRestartSec=10s\n"
        "NoNewPrivileges=yes\nPrivateTmp=yes\n"
        "\n[Install]\nWantedBy=multi-user.target\n"
    )


def owned_unit(installation, value) -> Path:
    directory = Path("/etc/systemd/system")
    reject_links(directory)
    for item in (directory, *directory.parents):
        if item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
            raise ValueError("E_STARTUP_UNIT_OWNERSHIP")
    path = directory / unit_name(installation)
    reject_links(path)
    if path.exists() and (
        value is None
        or not path.is_file()
        or path.stat().st_uid != 0
        or path.stat().st_mode & 0o022
        or sha256(path) != value["unitSha256"]
    ):
        raise ValueError("E_STARTUP_UNIT_OWNERSHIP")
    return path


def worker_bytes(installation, previous) -> bytes:
    if getattr(sys, "frozen", False):
        # Kernel-backed executing inode, even if a download pathname is replaced.
        selected = Path("/proc/self/exe")
    elif previous is not None:
        selected = installation.target / previous["workerFile"]
        reject_links(selected)
        if sha256(selected) != previous["workerSha256"]:
            raise ValueError("E_STARTUP_WORKER")
    else:
        raise ValueError("E_STARTUP_FROZEN_REQUIRED")
    with selected.open("rb") as stream:
        raw = stream.read(128 * 1024**2 + 1)
    architecture = installation.configuration["architecture"]
    machine = {"linux/amd64": 62, "linux/arm64": 183}.get(architecture)
    if (
        len(raw) < 64
        or len(raw) > 128 * 1024**2
        or raw[:6] != b"\x7fELF\x02\x01"
        or int.from_bytes(raw[18:20], "little") != machine
    ):
        raise ValueError("E_STARTUP_WORKER")
    return raw


def require_capability(worker: Path, target: Path) -> None:
    result = subprocess.run(
        [str(worker), "--capabilities"],
        cwd=target,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C"},
    )
    if result.returncode or len(result.stdout) > 16384:
        raise ValueError("E_STARTUP_WORKER")
    capability = json.loads(result.stdout, object_pairs_hook=unique_object)
    if (
        not isinstance(capability, dict)
        or type(capability.get("formatVersion")) is not int
        or capability["formatVersion"] != 1
        or capability.get("linuxComposeStart") is not True
    ):
        raise ValueError("E_STARTUP_FROZEN_REQUIRED")


def configure(target: Path, *, enabled: bool | None = None) -> dict:
    if (
        os.name != "posix"
        or os.geteuid() != 0
        or not Path("/run/systemd/system").is_dir()
    ):
        raise ValueError("E_UPDATE_SYSTEMD_REQUIRED")
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        previous = policy(installation)
        adapter = validate_runtime(installation)
        existing_update = installation.state.get("updatePolicy")
        if existing_update is not None:
            from update_worker import require_worker, validate_policy

            validate_policy(existing_update)
            require_worker(installation, existing_update)
            # An old scheduler must not silently recreate the base Compose
            # restart policy while ignoring the tracked startup overlay.
            if existing_update["enabled"]:
                require_capability(target / existing_update["workerFile"], target)
        selected = (
            previous["enabled"]
            if enabled is None and previous
            else True
            if enabled is None
            else enabled
        )
        if type(selected) is not bool:
            raise TypeError("E_STARTUP_POLICY")
        raw = worker_bytes(installation, previous)
        digest = hashlib.sha256(raw).hexdigest()
        name = "maintenance-" + digest[:32]
        installation.write(name, raw)
        worker = target / name
        worker.chmod(0o700)
        require_capability(worker, target)
        path = owned_unit(installation, previous)
        text = definition(installation, name)
        unit_hash = hashlib.sha256(text.encode()).hexdigest()
        if path.exists() and sha256(path) != unit_hash:
            systemctl("disable", "--now", path.name)
            path.unlink()
            systemctl("daemon-reload")
        if (
            OVERLAY in installation.state["files"]
            and installation.state["files"][OVERLAY]
            != hashlib.sha256(OVERLAY_TEXT.encode()).hexdigest()
        ):
            raise ValueError("E_STARTUP_UPGRADE_REQUIRED")
        installation.write(OVERLAY, OVERLAY_TEXT)
        installation.state["startupPolicy"] = {
            "formatVersion": 1,
            "enabled": selected,
            "workerFile": name,
            "workerSha256": digest,
            "unitSha256": unit_hash,
            "state": "registering",
            "machine": machine_binding(installation.state["installationId"]),
            "daemon": adapter.daemon,
        }
        installation.save()
        if not path.exists():
            publish_unit(path.parent, path.name, text)
        systemctl("daemon-reload")
        # Enable only. Starting a second lock-owning worker here would race the
        # active installer; its existing checked start applies the overlay now.
        systemctl("enable" if selected else "disable", path.name)
        if systemctl("show", path.name, "--property=UnitFileState", "--value") != (
            "enabled" if selected else "disabled"
        ):
            raise ValueError("E_STARTUP_REGISTRATION")
        installation.start()
        installation.state["startupPolicy"]["state"] = (
            "registered" if selected else "disabled"
        )
        installation.save()
        return {
            "enabled": selected,
            "unit": path.name,
            "runtimeHealthy": True,
            "bootVerified": False,
        }


def disable_owned(installation, *, remove=False) -> None:
    value = policy(installation)
    if value is None:
        return
    path = owned_unit(installation, value)
    if path.exists():
        systemctl("disable", "--now", path.name)
        if remove:
            path.unlink()
            systemctl("daemon-reload")
    value["enabled"] = False
    value["state"] = "removed" if remove else "disabled"
    installation.save()


def disable(target: Path) -> dict:
    require_root()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        disable_owned(installation)
        return {"enabled": False, "runningServicesStopped": False}


def status(target: Path) -> dict:
    require_root()
    validate_host(target)
    installation = load_installation(target, verify=False)
    value = policy(installation)
    if value is None:
        return {"configured": False, "bootVerified": False}
    path = owned_unit(installation, value)
    return {
        "configured": path.exists(),
        "enabled": value["enabled"],
        "unit": path.name,
        "unitState": systemctl("show", path.name, "--property=ActiveState", "--value")
        if path.exists()
        else "missing",
        "lastStartup": installation.state.get("platformStartupAttempt"),
        "bootVerified": False,
    }


def background_start(target: Path) -> dict:
    require_root()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target, verify=False)
        require_bound(installation)
        value = policy(installation)
        if value is None or value["state"] == "removed":
            raise ValueError("E_STARTUP_POLICY")
        worker = target / value["workerFile"]
        reject_links(worker)
        if (
            installation.state["files"].get(value["workerFile"])
            != value["workerSha256"]
            or sha256(worker) != value["workerSha256"]
        ):
            raise ValueError("E_STARTUP_WORKER")
        from update_gate import fenced

        if (
            installation.state.get("authority") is not None
            or installation.state.get("preparedForRestore")
            or fenced(installation.state)
            or installation.state.get("stage") == "uninstalled"
            or not value["enabled"]
        ):
            outcome = {"healthy": False, "deferred": True}
        else:
            installation.verify_files()
            validate_runtime(installation)
            installation.state["platformStartupAttempt"] = {
                "at": int(time.time()),
                "healthy": False,
                "deferred": False,
                "state": "starting",
            }
            installation.save()
            try:
                installation.start()
            except (OSError, ValueError, subprocess.SubprocessError):
                installation.state["platformStartupAttempt"]["state"] = "failed"
                installation.save()
                raise
            outcome = {"healthy": True, "deferred": False}
        installation.state["platformStartupAttempt"] = {
            "at": int(time.time()),
            "state": "deferred" if outcome["deferred"] else "complete",
            **outcome,
        }
        installation.save()
        return outcome
