"""Fixed owned Windows machine task / Linux systemd timer for update checks."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

from host import reject_links


def publish_unit(directory: Path, name: str, text: str) -> None:
    """Publish a complete unit without replacing a pre-existing directory entry."""
    if not re.fullmatch(r"kyrion-[a-f0-9-]{36}-updates\.(service|timer)", name):
        raise ValueError("E_UPDATE_UNIT_OWNERSHIP")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".kyrion-unit-", dir=directory, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text.encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        # Incomplete staging files are inert. The active unit is published only
        # after all bytes are durable and its expected hash was journaled.
        os.link(temporary, directory / name, follow_symlinks=False)
        if os.name == "posix":
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def linux_plan(identifier: str, target: str, worker: str) -> dict[str, str]:
    identifier = str(uuid.UUID(identifier))
    if not re.fullmatch(r"/[A-Za-z0-9/_-]+", target) or not re.fullmatch(
        r"maintenance-[a-f0-9]{32}", worker
    ):
        raise ValueError("E_UPDATE_WORKER")
    name = "kyrion-" + identifier + "-updates"
    return {
        name + ".service": (
            "[Unit]\nDescription=Kyrion signed release check "
            + identifier
            + "\nAfter=network-online.target\nWants=network-online.target\n"
            "\n[Service]\nType=oneshot\nUser=root\nUMask=0077\n"
            "ExecStart="
            + target
            + "/"
            + worker
            + " --background-update-check --target "
            + target
            + "\nWorkingDirectory="
            + target
            + "\nTimeoutStartSec=10min\nNoNewPrivileges=yes\nPrivateTmp=yes\n"
        ),
        name + ".timer": (
            "[Unit]\nDescription=Kyrion daily release check "
            + identifier
            + "\n\n[Timer]\nOnBootSec=2min\nOnUnitActiveSec=24h\n"
            "AccuracySec=1min\nUnit=" + name + ".service\n"
            "\n[Install]\nWantedBy=timers.target\n"
        ),
    }


def systemctl(*arguments: str) -> str:
    result = subprocess.run(
        ["/usr/bin/systemctl", *arguments],
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "SYSTEMD_PAGER": "cat"},
        capture_output=True,
        timeout=45,
        check=False,
    )
    if result.returncode or len(result.stdout) > 16384:
        raise ValueError("E_UPDATE_SYSTEMD")
    return result.stdout.decode("ascii", errors="strict").strip()


def operate(installation, action: str) -> dict:
    if action not in {"register", "remove"}:
        raise ValueError("E_UPDATE_SCHEDULE")
    from update_worker import require_worker

    policy = installation.state["updatePolicy"]
    require_worker(installation, policy)
    if os.name == "nt":
        from windows_tasks import operate as task_operation
        from windows_tasks import update_check_plan

        plan = update_check_plan(
            installation.state["installationId"],
            str(installation.target),
            policy["workerFile"],
        )
        if action == "remove":
            task_operation(plan, "stop")
        actual = task_operation(plan, action)
        return {
            "state": "registered" if actual["registered"] else "removed",
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
    for path in (directory, *directory.parents):
        if path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise ValueError("E_UPDATE_UNIT_OWNERSHIP")
    units = linux_plan(
        installation.state["installationId"],
        str(installation.target),
        policy["workerFile"],
    )
    hashes = {
        name: hashlib.sha256(text.encode()).hexdigest() for name, text in units.items()
    }
    previous = installation.state.get("updateSchedule", {}).get("units", {})
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
            raise ValueError("E_UPDATE_UNIT_OWNERSHIP")
    timer = next(name for name in units if name.endswith(".timer"))
    if action == "register":
        installation.state["updateSchedule"] = {"state": "registering", "units": hashes}
        installation.save()
        for name, text in units.items():
            path = directory / name
            if not path.exists():
                publish_unit(directory, name, text)
        systemctl("daemon-reload")
        systemctl("enable", "--now", timer)
        if (
            systemctl("is-enabled", timer) != "enabled"
            or systemctl("is-active", timer) != "active"
        ):
            raise ValueError("E_UPDATE_SYSTEMD")
    else:
        # An interrupted registration may have created neither or only one file.
        # The recorded unit hashes still bind every file that may be removed.
        if (directory / timer).exists():
            systemctl("disable", "--now", timer)
        service = next(name for name in units if name.endswith(".service"))
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
