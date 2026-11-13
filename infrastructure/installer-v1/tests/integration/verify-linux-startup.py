"""Execute the frozen startup fence under real systemd in an owned guest.

No application stack is installed here. The fixture verifies service invocation,
durable deferral and worker integrity, not successful application boot or SSO.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bundle import sha256
from linux_startup import definition, machine_binding, unit_name
from recovery import load_installation
from runtime import Installation
from update_schedule import publish_unit, systemctl


def verify(worker: Path, parent: Path) -> dict:
    marker = json.loads(Path("/work/kyrion-systemd-fixture.json").read_bytes())
    if (
        sys.platform != "linux"
        or os.geteuid() != 0
        or marker.get("scope") != "installer-systemd-development-fixture"
        or Path("/proc/1/comm").read_text().strip() != "systemd"
        or parent != Path("/work/startup-service-tests")
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    parent.mkdir(mode=0o700, exist_ok=True)
    for item in (parent, *parent.parents):
        if item.is_symlink() or item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
            raise ValueError("E_TEST_ENVIRONMENT")
    root = parent / uuid.uuid4().hex
    installation = Installation(
        root,
        {"release": "1.0.0", "architecture": "linux/amd64"},
        "a" * 64,
        "fixture.test",
        "10.231.0.1",
    )
    raw = worker.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    name = "maintenance-" + digest[:32]
    installation.write(name, raw)
    (root / name).chmod(0o700)
    capability = json.loads(
        subprocess.check_output([str(root / name), "--capabilities"], timeout=30)
    )
    if capability.get("linuxComposeStart") is not True:
        raise ValueError("E_TEST_WORKER")
    text = definition(installation, name)
    installation.state["startupPolicy"] = {
        "formatVersion": 1,
        "enabled": True,
        "workerFile": name,
        "workerSha256": digest,
        "unitSha256": hashlib.sha256(text.encode()).hexdigest(),
        "state": "registered",
        "machine": machine_binding(installation.state["installationId"]),
        "daemon": {"id": "fixture-not-probed", "sockets": ["/run/docker.sock"]},
    }
    installation.state["updateTransaction"] = {"phase": "migrating"}
    installation.save()
    unit = unit_name(installation)
    path = Path("/etc/systemd/system") / unit
    if path.exists() or path.is_symlink():
        raise ValueError("E_TEST_FOREIGN_UNIT")
    publish_unit(path.parent, path.name, text)
    try:
        systemctl("daemon-reload")
        systemctl("enable", unit)
        systemctl("start", unit)
        state = load_installation(root, verify=False).state
        if state.get("platformStartupAttempt", {}).get("deferred") is not True:
            raise ValueError("E_TEST_FENCE")
        if systemctl("show", unit, "--property=ActiveState", "--value") != "active":
            raise ValueError("E_TEST_SERVICE")
        # Corrupt only this disposable worker. Verify actual service execution
        # fails and exhausts the configured three-start budget without writers.
        systemctl("stop", unit)
        with (root / name).open("ab") as stream:
            stream.write(b"fixture integrity violation")
        systemctl("reset-failed", unit)
        systemctl("start", "--no-block", unit)
        deadline = time.monotonic() + 55
        while time.monotonic() < deadline:
            attempts = systemctl("show", unit, "--property=NRestarts", "--value")
            active = systemctl("show", unit, "--property=ActiveState", "--value")
            if attempts == "3" and active == "failed":
                break
            time.sleep(1)
        else:
            raise ValueError("E_TEST_START_LIMIT")
        # Some systemd versions preserve Result=exit-code when the next start
        # is rate limited. Verify executed invocations and a stable stopped unit.
        time.sleep(11)
        if (
            systemctl("show", unit, "--property=NRestarts", "--value") != "3"
            or systemctl("show", unit, "--property=ActiveState", "--value") != "failed"
        ):
            raise ValueError("E_TEST_START_LIMIT")
        journal = subprocess.check_output(
            ["journalctl", "-u", unit, "-o", "json", "--no-pager"], timeout=30
        )
        failures = sum(
            json.loads(line).get("MESSAGE") == "E_PLATFORM_STARTUP"
            for line in journal.splitlines()
        )
        if failures != 3:
            raise ValueError("E_TEST_START_LIMIT")
        return {
            "actualSystemdWorkerExecuted": True,
            "unfinishedUpdateDeferred": True,
            "changedWorkerRejected": True,
            "threeStartBudgetExhausted": True,
            "applicationStackStarted": False,
            "coldBootVerified": False,
            "workerSha256": digest,
            "fixture": str(root),
        }
    finally:
        if sha256(path) != hashlib.sha256(text.encode()).hexdigest():
            raise ValueError("E_TEST_UNIT_CHANGED")
        systemctl("disable", "--now", unit)
        systemctl("reset-failed", unit)
        path.unlink()
        systemctl("daemon-reload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.worker, Path("/work/startup-service-tests"))
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
