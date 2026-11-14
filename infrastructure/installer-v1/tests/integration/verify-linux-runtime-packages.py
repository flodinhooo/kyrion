"""Actual Debian package/tool/unit-file tests; no daemon/system boot acceptance."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/kyrion-installer")
import linux_packages as packages
import linux_runtime
from recovery import load_installation
from runtime import Installation


def main():
    marker_path = Path("/etc/kyrion-crypto-package-fixture.json")
    marker = json.loads(marker_path.read_bytes())
    root = Path("/").stat()
    if (
        os.geteuid() != 0
        or marker_path.stat().st_uid != 0
        or marker_path.stat().st_mode & 0o077
        or marker.get("scope") != "installer-crypto-package-development-fixture"
        or marker.get("purpose") != "runtime"
        or (marker.get("rootDevice"), marker.get("rootInode"))
        != (root.st_dev, root.st_ino)
        or not packages.supported()
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    if any(
        Path(path).exists()
        for path in ("/usr/bin/docker", "/usr/sbin/dockerd", "/usr/bin/gpg")
    ):
        raise ValueError("E_TEST_NOT_CLEAN")
    target = Path("/work/installed")
    if target.exists():
        raise ValueError("E_TEST_TARGET_EXISTS")
    Installation(
        target,
        {"release": "1.0.0", "architecture": "linux/amd64"},
        "a" * 64,
        "fixture.test",
        "10.231.0.1",
    )
    reviews = []

    def approve(summary):
        reviews.append(summary)
        return True  # Marked developer chroot; service starts denied by policy.

    result = packages.configure(
        target, spec=packages.RUNTIME, ready=linux_runtime.tools_ready, review=approve
    )
    installation = load_installation(target)
    if (
        not result["available"]
        or not result["packagesChanged"]
        or installation.state["runtimePrerequisite"]["phase"] != "complete"
        or len(reviews) != 2
    ):
        raise ValueError("E_TEST_RUNTIME_PACKAGES")
    # Actual installed distribution unit/files/owner/dpkg checks, without
    # pretending a service is registered/running inside this chroot.
    fragment = Path("/usr/lib/systemd/system/docker.service")
    if not fragment.is_file():
        fragment = Path("/lib/systemd/system/docker.service")
    linux_runtime.verify_vendor_file(installation, fragment)
    if Path("/run/docker.sock").exists():
        raise ValueError("E_TEST_UNEXPECTED_DAEMON_START")
    repeated = packages.configure(
        target,
        spec=packages.RUNTIME,
        ready=linux_runtime.tools_ready,
        review=lambda _: False,
    )
    if not repeated["available"] or repeated["packagesChanged"]:
        raise ValueError("E_TEST_RUNTIME_REPEAT")
    report = {
        "actualDebian13Chroot": True,
        "actualInitiallyMissingDockerAndGnuPG": True,
        "actualReviewedPinnedPackageInstallation": True,
        "actualDockerCliAndComposeProbes": True,
        "actualGnuPGProbes": True,
        "actualVendorUnitOwnershipAndDpkgIntegrityVerified": True,
        "actualRepeatWithoutPackageChanges": True,
        "packages": installation.state["runtimePrerequisite"]["packages"],
        "dockerVersion": packages.run(installation, "docker", "--version").strip(),
        "composeVersion": packages.run(
            installation, "docker", "compose", "version", "--short"
        ).strip(),
        "dockerDaemonStarted": False,
        "systemBootAccepted": False,
        "applicationInstallationAccepted": False,
    }
    Path("/work/report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
