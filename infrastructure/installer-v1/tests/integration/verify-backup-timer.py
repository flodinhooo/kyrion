"""Actual owned backup timer/worker/store tests in a marked disposable guest.

A synthetic update fence prevents capture. This establishes real scheduled
invocation and deferral, not application backup/restore or physical boot.
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
import backup_store
from backup_schedule import operate
from backup_worker import remove_schedule
from recovery import load_installation
from runtime import Installation


def verify(worker: Path) -> dict:
    marker = json.loads(Path("/work/kyrion-systemd-fixture.json").read_bytes())
    if (
        sys.platform != "linux"
        or os.geteuid() != 0
        or marker.get("scope") != "installer-systemd-development-fixture"
        or Path("/proc/1/comm").read_text().strip() != "systemd"
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    parent = Path("/work/backup-timer-tests")
    parent.mkdir(mode=0o700, exist_ok=True)
    backup_store.secure_directory(parent)
    identifier = uuid.uuid4().hex
    target = parent / ("installed-" + identifier)
    installation = Installation(
        target,
        {"release": "1.0.0", "architecture": "linux/amd64"},
        "a" * 64,
        "fixture.test",
        "10.231.0.1",
    )
    raw = worker.read_bytes()
    name = "maintenance-" + hashlib.sha256(raw).hexdigest()[:32]
    installation.write(name, raw)
    (target / name).chmod(0o700)
    capabilities = json.loads(
        subprocess.check_output([str(target / name), "--capabilities"], timeout=30)
    )
    if capabilities.get("backupProtocol") != 1:
        raise ValueError("E_TEST_WORKER")
    binding = backup_store.prepare(installation, parent / ("store-" + identifier))
    key_hash = backup_store.prepare_key(
        installation,
        parent / ("recovery-" + identifier + ".key"),
        Path(binding["path"]),
    )
    installation.state["backupPolicy"] = {
        "formatVersion": 1,
        "revision": str(uuid.uuid4()),
        "enabled": True,
        "workerFile": name,
        "utcDays": [1, 2, 3, 4, 5, 6, 7],
        "startMinute": 0,
        "durationMinutes": 1440,
        "keep": 2,
        "store": binding,
        "keySha256": key_hash,
    }
    installation.state["updateTransaction"] = {"phase": "migrating"}
    installation.save()
    registered = False
    try:
        actual = operate(installation, "register")
        registered = True
        installation.state["backupSchedule"] = actual
        installation.save()
        if operate(installation, "inspect")["state"] != "registered":
            raise ValueError("E_TEST_BACKUP_REGISTRATION")
        service = actual["name"].removesuffix(".timer") + ".service"
        deadline = time.monotonic() + 165
        found = False
        while time.monotonic() < deadline:
            journal = subprocess.check_output(
                ["journalctl", "-u", service, "-o", "json", "--no-pager"], timeout=15
            )
            for line in journal.splitlines():
                message = json.loads(line).get("MESSAGE", "")
                try:
                    outcome = json.loads(message)
                except (ValueError, TypeError):
                    continue
                if outcome == {"completed": False, "deferred": True}:
                    found = True
                    break
            if found:
                break
            time.sleep(1)
        if not found:
            raise ValueError("E_TEST_BACKUP_TIMER_EXECUTION")
        saved = load_installation(target).state
        if saved.get("backupRun") is not None or saved.get("backupHistory"):
            raise ValueError("E_TEST_BACKUP_FENCE")
        backup_store.verify(installation, binding)
        backup_store.read_key(installation, key_hash)
        return {
            "actualSystemdBackupTimerRegistered": True,
            "actualDefaultBootTimerExecutedFrozenWorker": True,
            "actualUpdateFenceDeferredCapture": True,
            "actualStoreAndKeyOwnershipVerified": True,
            "syntheticInstallationJournal": True,
            "applicationCaptureExecuted": False,
            "applicationRestoreVerified": False,
            "coldBootVerified": False,
            "workerSha256": hashlib.sha256(raw).hexdigest(),
        }
    finally:
        if registered or installation.state.get("backupSchedule") is not None:
            remove_schedule(load_installation(target))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.worker)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
