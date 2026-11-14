"""Real scheduled application backup in the explicitly owned systemd guest.

Requires a completed verify-systemd-stack fixture. Runs its frozen installer,
real timer, Core/PostgreSQL and GnuPG. Namespace drop-ins belong only to this
developer fixture. No application, timer or cryptographic probes are injected.
This does not establish physical reboot or portable database import acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pty
import select
import subprocess
import sys
import tarfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import backup_store
from backup_schedule import linux_backup_plan
from backup_worker import disable
from linux_startup import disable_owned, unit_name
from onboarding import CoreClient
from recovery import load_installation, verified_plaintext
from update_schedule import systemctl

NETWORK = "[Service]\nNetworkNamespacePath=/run/netns/kyrion-installer-fixture\n"


def dialogue(worker: Path, target: Path, arguments: list[str], answers: str) -> None:
    master, slave = pty.openpty()
    process = None
    output = bytearray()
    try:
        process = subprocess.Popen(
            [str(worker), *arguments, "--target", str(target)],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)
        slave = None
        os.write(master, answers.encode("utf-8"))
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if select.select([master], [], [], 1)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
                if len(output) > 1024**2:
                    raise ValueError("E_TEST_DIALOGUE_LIMIT")
            if process.poll() is not None:
                break
        if process.poll() is None:
            process.terminate()
        if process.wait(timeout=30):
            with os.fdopen(
                os.open(
                    target.parent / "private-backup-dialogue.log",
                    os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                    0o600,
                ),
                "wb",
            ) as stream:
                stream.write(output)
            raise ValueError("E_TEST_BACKUP_CONFIGURATION")
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=30)
        os.close(master)
        if slave is not None:
            os.close(slave)


def verify(root: Path, worker: Path) -> dict:
    if (
        os.geteuid() != 0
        or root.parent != Path("/work/systemd-stack-fixtures")
        or root.is_symlink()
        or json.loads((root / "fixture.json").read_bytes()).get("scope")
        != "installer-systemd-stack-fixture"
        or json.loads(Path("/work/kyrion-systemd-fixture.json").read_bytes()).get(
            "scope"
        )
        != "installer-systemd-development-fixture"
        or not json.loads((root / "report.json").read_bytes()).get(
            "actualRecoveryWithPreservedIdentity"
        )
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    target = root / "installed"
    installation = load_installation(target)
    previous = installation.state.get("backupPolicy")
    if previous is not None and (
        previous.get("enabled") is not False
        or installation.state.get("backupRun", {}).get("phase") != "complete"
    ):
        raise ValueError("E_TEST_COMPLETED_DISABLED_POLICY_REQUIRED")
    prior_history = len(installation.state.get("backupHistory", []))
    original = (target / "data/knowledge/fixture.txt").read_bytes()
    access = root / "private-test-access.json"
    if access.stat().st_uid != 0 or access.stat().st_mode & 0o777 != 0o600:
        raise ValueError("E_TEST_PRIVATE_ACCESS")
    credentials = json.loads(access.read_bytes())["login"]
    worker_hash = hashlib.sha256(worker.read_bytes()).hexdigest()
    name = "maintenance-" + worker_hash[:32]
    plans = linux_backup_plan(installation.state["installationId"], str(target), name)
    service = next(name for name in plans if name.endswith(".service"))
    dropins = []
    try:
        for unit in (unit_name(installation), service):
            directory = Path("/etc/systemd/system") / (unit + ".d")
            directory.mkdir(mode=0o700, exist_ok=False)
            dropin = directory / "fixture-network.conf"
            dropin.write_text(NETWORK, encoding="utf-8")
            dropin.chmod(0o600)
            dropins.append(dropin)
        dialogue(
            worker,
            target,
            ["--autostart", "enable"],
            "en\nMAINTAIN\nCONFIGURE-STARTUP\n",
        )
        client = CoreClient(load_installation(target))
        client.session = client.request("POST", "/v1/auth/login", credentials)[
            "sessionToken"
        ]
        original_user = client.request("GET", "/v1/auth/me")["id"]
        attempt_id = uuid.uuid4().hex
        destination = root / ("scheduled-backups-" + attempt_id)
        exported = root / ("scheduled-backup-recovery-" + attempt_id + ".key")
        dialogue(
            worker,
            target,
            ["--backup-schedule", "configure"],
            f"en\nMAINTAIN\n{destination}\n{exported}\n\n00:00\n1440\n2\nCONFIGURE-BACKUPS\n",
        )
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            installation = load_installation(target, verify=False)
            attempt = installation.state.get("backupAttempt", {})
            if attempt.get("error"):
                raise ValueError("E_TEST_SCHEDULED_CAPTURE")
            if (
                installation.state.get("backupRun", {}).get("phase") == "complete"
                and installation.state["backupRun"]["policyRevision"]
                == installation.state["backupPolicy"]["revision"]
            ):
                break
            time.sleep(2)
        else:
            raise ValueError("E_TEST_SCHEDULED_CAPTURE_TIMEOUT")
        run = installation.state["backupRun"]
        if run["actor"] != "AUTOMATIC" or run["attempts"] != 1:
            raise ValueError("E_TEST_AUTOMATIC_CAPTURE")
        policy = installation.state["backupPolicy"]
        password = backup_store.read_key(installation, policy["keySha256"])
        archive_path = destination / run["name"]
        with verified_plaintext(archive_path, password, private_parent=target) as (
            archive,
            manifest,
            _scratch,
        ):
            with tarfile.open(archive, "r:") as content:
                member = content.extractfile("data/knowledge/fixture.txt")
                if member is None or member.read(len(original) + 1) != original:
                    raise ValueError("E_TEST_CAPTURE_CONTENT")
            if (
                manifest["metadata"]["scheduledBackupRunId"] != run["id"]
                or manifest["metadata"]["installationId"]
                != installation.state["installationId"]
            ):
                raise ValueError("E_TEST_CAPTURE_CONTENT")
        installation.check_health()
        client = CoreClient(installation)
        client.session = client.request("POST", "/v1/auth/login", credentials)[
            "sessionToken"
        ]
        if client.request("GET", "/v1/auth/me")["id"] != original_user:
            raise ValueError("E_TEST_ACCOUNT_PRESERVATION")
        systemctl("start", service)
        repeated = load_installation(target)
        if (
            not repeated.state["backupAttempt"]["alreadyCompletedSlot"]
            or len(repeated.state["backupHistory"]) != prior_history + 1
        ):
            raise ValueError("E_TEST_DUPLICATE_CAPTURE")
        return {
            "actualNativeConfiguration": True,
            "actualTimerAutomaticApplicationCapture": True,
            "actualEncryptedArchiveContentVerified": True,
            "actualApplicationHealthAndLoginAfterCapture": True,
            "actualSameSlotDuplicatePrevention": True,
            "probesInjected": False,
            "fixtureNamespaceDropins": True,
            "portableDatabaseImportVerified": False,
            "coldBootVerified": False,
        }
    finally:
        installation = load_installation(target, verify=False)
        if installation.state.get("backupPolicy") is not None:
            disable(target)
        disable_owned(load_installation(target, verify=False), remove=True)
        installation.compose("down", "--timeout", "30")
        for dropin in dropins:
            if dropin.is_symlink() or dropin.read_text(encoding="utf-8") != NETWORK:
                raise ValueError("E_TEST_DROPIN_CHANGED")
            dropin.unlink()
            dropin.parent.rmdir()
        systemctl("daemon-reload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.worker)
    with (args.root / "installed-backup-report.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
