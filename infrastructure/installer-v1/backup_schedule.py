"""Owned backup task/timer using the existing fixed scheduler primitives."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from backup_policy import validate
from host import reject_links
from update_schedule import linux_plan, publish_unit, systemctl


def linux_backup_plan(identifier: str, target: str, worker: str) -> dict[str, str]:
    source = linux_plan(identifier, target, worker, automatic=True)
    return {
        name.replace("-updates.", "-backups."): text.replace("-updates.", "-backups.")
        .replace("Kyrion signed release check", "Kyrion consistent backup")
        .replace("Kyrion daily release check", "Kyrion backup window check")
        .replace("--background-update-check", "--background-backup")
        .replace("After=network-online.target\nWants=network-online.target\n", "")
        .replace("OnUnitActiveSec=1h", "OnUnitActiveSec=15min")
        for name, text in source.items()
    }


def operate(installation, action: str) -> dict:
    if action not in {"register", "remove", "inspect"}:
        raise ValueError("E_BACKUP_SCHEDULE")
    from backup_worker import require_worker

    policy = installation.state["backupPolicy"]
    validate(policy)
    require_worker(installation, policy)
    if os.name == "nt":
        from windows_tasks import backup_plan
        from windows_tasks import operate as task_operation

        plan = backup_plan(
            installation.state["installationId"],
            str(installation.target),
            policy["workerFile"],
        )
        if action == "remove":
            task_operation(plan, "stop")
        actual = task_operation(plan, action)
        return {
            "state": "registered"
            if actual["registered"]
            else "removed"
            if action == "remove"
            else "missing",
            "backend": "windows-task",
            "name": plan["name"],
            "coldBootVerified": False,
        }
    if (
        os.name != "posix"
        or os.geteuid() != 0
        or not Path("/run/systemd/system").is_dir()
    ):
        raise ValueError("E_UPDATE_SYSTEMD_REQUIRED")
    directory = Path("/etc/systemd/system")
    reject_links(directory)
    for item in (directory, *directory.parents):
        if item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
            raise ValueError("E_BACKUP_SCHEDULE_OWNER")
    units = linux_backup_plan(
        installation.state["installationId"],
        str(installation.target),
        policy["workerFile"],
    )
    hashes = {
        name: hashlib.sha256(text.encode()).hexdigest() for name, text in units.items()
    }
    previous = installation.state.get("backupSchedule", {}).get("units", {})
    for name, text in units.items():
        path = directory / name
        reject_links(path)
        if path.exists() and (
            previous.get(name) != hashes[name]
            or not path.is_file()
            or path.stat().st_uid != 0
            or path.stat().st_mode & 0o022
            or path.read_bytes() != text.encode()
        ):
            raise ValueError("E_BACKUP_SCHEDULE_OWNER")
    timer = next(name for name in units if name.endswith(".timer"))
    service = next(name for name in units if name.endswith(".service"))
    if action == "inspect":
        present = all((directory / name).is_file() for name in units)
        active = (
            present
            and systemctl("show", timer, "--property=ActiveState", "--value")
            == "active"
        )
        enabled = (
            present
            and systemctl("show", timer, "--property=UnitFileState", "--value")
            == "enabled"
        )
        return {
            "state": "registered"
            if active and enabled
            else "inactive"
            if present
            else "missing",
            "backend": "systemd-timer",
            "name": timer,
            "coldBootVerified": False,
        }
    if action == "register":
        installation.state["backupSchedule"] = {"state": "registering", "units": hashes}
        installation.save()
        for name, text in units.items():
            if not (directory / name).exists():
                publish_unit(directory, name, text)
        systemctl("daemon-reload")
        systemctl("enable", "--now", timer)
        if (
            systemctl("is-enabled", timer) != "enabled"
            or systemctl("is-active", timer) != "active"
        ):
            raise ValueError("E_BACKUP_SCHEDULE")
    else:
        if (directory / timer).exists():
            systemctl("disable", "--now", timer)
        if (directory / service).exists():
            systemctl("stop", service)
        for name in units:
            (directory / name).unlink(missing_ok=True)
        systemctl("daemon-reload")
    return {
        "state": "registered" if action == "register" else "removed",
        "backend": "systemd-timer",
        "name": timer,
        "units": hashes,
        "coldBootVerified": False,
    }
