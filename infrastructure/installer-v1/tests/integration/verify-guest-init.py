"""Two-phase real init-restart test for the marked disposable Linux guest.

Prepare under the fixture Docker namespace, restart only the owned guest using
its verified host driver, then verify under the new Docker namespace. No reboot
is initiated here. An explicit checkpoint UUID permits repeat tests without
overwriting evidence. WSL may retain its shared kernel across guest init restart.
"""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from linux_startup import disable_owned, unit_name
from onboarding import CoreClient
from recovery import load_installation
from update_compose import Compose
from update_schedule import systemctl

NETWORK = "[Service]\nNetworkNamespacePath=/run/netns/kyrion-installer-fixture\n"


def guarded(root: Path):
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
        or Path("/proc/1/comm").read_text().strip() != "systemd"
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    return load_installation(root / "installed")


def start_ticks() -> str:
    return Path("/proc/1/stat").read_text().rsplit(")", 1)[1].split()[19]


def client(installation, root: Path) -> CoreClient:
    access = root / "private-test-access.json"
    if access.stat().st_uid != 0 or access.stat().st_mode & 0o777 != 0o600:
        raise ValueError("E_TEST_PRIVATE_ACCESS")
    credentials = json.loads(access.read_bytes())["login"]
    value = CoreClient(installation)
    value.session = value.request("POST", "/v1/auth/login", credentials)["sessionToken"]
    return value


def prepare(root: Path, worker: Path, checkpoint: Path) -> dict:
    installation = guarded(root)
    if (
        not json.loads((root / "installed-backup-report.json").read_bytes()).get(
            "actualApplicationHealthAndLoginAfterCapture"
        )
        or installation.state["updateTransaction"]["phase"] != "recovered"
        or installation.state["backupPolicy"]["enabled"] is not False
        or checkpoint.exists()
    ):
        raise ValueError("E_TEST_COMPLETED_FIXTURE_REQUIRED")
    unit = unit_name(installation)
    directory = Path("/etc/systemd/system") / (unit + ".d")
    directory.mkdir(mode=0o700, exist_ok=True)
    dropin = directory / "fixture-network.conf"
    if dropin.is_symlink() or (
        dropin.exists() and dropin.read_text(encoding="utf-8") != NETWORK
    ):
        raise ValueError("E_TEST_DROPIN_CHANGED")
    dropin.write_text(NETWORK, encoding="utf-8")
    dropin.chmod(0o600)
    helper = runpy.run_path(
        str(Path(__file__).with_name("verify-installed-backup.py")),
        run_name="guest_init_helpers",
    )
    helper["dialogue"](
        worker,
        installation.target,
        ["--autostart", "enable"],
        "en\nMAINTAIN\nCONFIGURE-STARTUP\n",
    )
    installation = load_installation(installation.target)
    if systemctl("is-enabled", unit) != "enabled":
        raise ValueError("E_TEST_BOOT_REGISTRATION")
    before = {
        "scope": "installer-systemd-guest-boot-fixture",
        "bootId": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "initStartTicks": start_ticks(),
        "identity": Compose(installation).identity(),
        "userId": client(installation, root).request("GET", "/v1/auth/me")["id"],
        "unit": unit,
        "at": int(time.time()),
    }
    systemctl("stop", unit)
    installation.compose("down", "--timeout", "30")
    with os.fdopen(
        os.open(checkpoint, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        json.dump(before, stream)
    return {"ownFixtureReadyForGuestRestart": True, "unit": unit}


def verify(root: Path, checkpoint: Path) -> dict:
    installation = guarded(root)
    if checkpoint.stat().st_uid != 0 or checkpoint.stat().st_mode & 0o777 != 0o600:
        raise ValueError("E_TEST_PRIVATE_CHECKPOINT")
    before = json.loads(checkpoint.read_bytes())
    if (
        before.get("scope") != "installer-systemd-guest-boot-fixture"
        or before["unit"] != unit_name(installation)
        or start_ticks() == before["initStartTicks"]
    ):
        raise ValueError("E_TEST_INIT_NOT_RESTARTED")
    attempt = installation.state["platformStartupAttempt"]
    if (
        not attempt["healthy"]
        or attempt["deferred"]
        or attempt["at"] < before["at"]
        or systemctl("is-enabled", before["unit"]) != "enabled"
        or systemctl("show", before["unit"], "--property=ActiveState", "--value")
        != "active"
        or Compose(installation).identity() != before["identity"]
        or subprocess.check_output(["/usr/sbin/ip", "route", "show", "default"]).strip()
    ):
        raise ValueError("E_TEST_GUEST_BOOT_HEALTH")
    installation.check_health()
    if (
        client(installation, root).request("GET", "/v1/auth/me")["id"]
        != before["userId"]
    ):
        raise ValueError("E_TEST_GUEST_BOOT_IDENTITY")
    report = {
        "actualLinuxGuestInitRestart": True,
        "sharedKernelRestarted": Path("/proc/sys/kernel/random/boot_id")
        .read_text()
        .strip()
        != before["bootId"],
        "actualEnabledSystemdStartup": True,
        "actualApplicationTlsHealthAfterRestart": True,
        "actualOfflineSameIdentityLogin": True,
        "actualIdentityPreserved": True,
        "networkDefaultRouteAbsent": True,
        "interactiveLinuxLoginUsed": False,
        "physicalColdBootVerified": False,
        "windowsPreLoginBootVerified": False,
        "fixtureNamespaceDropin": True,
    }
    # Clean only after proof succeeds. Failed state remains for diagnosis.
    disable_owned(installation, remove=True)
    installation.compose("down", "--timeout", "30")
    dropin = (
        Path("/etc/systemd/system") / (before["unit"] + ".d") / "fixture-network.conf"
    )
    if dropin.is_symlink() or dropin.read_text(encoding="utf-8") != NETWORK:
        raise ValueError("E_TEST_DROPIN_CHANGED")
    dropin.unlink()
    dropin.parent.rmdir()
    systemctl("daemon-reload")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--attempt", type=uuid.UUID, required=True)
    args = parser.parse_args()
    checkpoint = args.root / ("private-guest-init-" + args.attempt.hex + ".json")
    if args.phase == "prepare":
        if args.worker is None:
            parser.error("prepare requires --worker")
        result = prepare(args.root, args.worker, checkpoint)
    else:
        result = verify(args.root, checkpoint)
        with (args.root / ("guest-init-report-" + args.attempt.hex + ".json")).open(
            "x", encoding="utf-8"
        ) as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result))
