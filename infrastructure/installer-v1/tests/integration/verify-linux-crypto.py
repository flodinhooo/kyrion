"""Real Debian tool/no-change reuse evidence in the marked developer guest.

This intentionally does not uninstall GnuPG to manufacture a missing-tool host.
It proves actual probes/APT simulation, not a clean-system package installation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import backup_store
import linux_crypto
from runtime import Installation


def verify() -> dict:
    marker = json.loads(Path("/work/kyrion-systemd-fixture.json").read_bytes())
    if (
        os.geteuid() != 0
        or marker.get("scope") != "installer-systemd-development-fixture"
        or not linux_crypto.supported()
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    parent = Path("/work/crypto-prerequisite-tests")
    parent.mkdir(mode=0o700, exist_ok=True)
    backup_store.secure_directory(parent)
    target = parent / uuid.uuid4().hex
    installation = Installation(
        target,
        {"release": "1.0.0", "architecture": "linux/amd64"},
        "a" * 64,
        "fixture.test",
        "10.231.0.1",
    )
    if not linux_crypto.available(installation):
        raise ValueError("E_TEST_PREREQUISITE")

    def forbid_review(_summary):
        raise ValueError("E_TEST_UNEXPECTED_PACKAGE_MUTATION")

    result = linux_crypto.configure(target, review=forbid_review)
    if not result["available"] or result["packagesChanged"]:
        raise ValueError("E_TEST_PACKAGE_REUSE")
    rows = linux_crypto.plan_rows(
        linux_crypto.run(
            installation,
            "apt-get",
            *linux_crypto.OPTIONS,
            "--simulate",
            "install",
            "gnupg",
        )
    )
    if rows:
        raise ValueError("E_TEST_UNEXPECTED_PACKAGE_PLAN")
    unfinished = linux_crypto.pending(installation)
    return {
        "actualDebian13": True,
        "actualGpgAndGpgconfProbed": True,
        "actualOwnedExecutableValidation": True,
        "actualAptSimulationParsed": True,
        "actualInstalledPackageReuse": True,
        "unconfiguredPackageCount": len(unfinished),
        "metadataRefreshed": False,
        "packagesInstalled": False,
        "cleanSystemPackageInstallationAccepted": False,
        "applicationBackupExecuted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
