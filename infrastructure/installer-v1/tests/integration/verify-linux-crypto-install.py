"""Actual package installation only inside an explicitly prepared fresh chroot."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/opt/kyrion-installer")
import linux_crypto
from recovery import crypto, load_installation
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
        or (marker.get("rootDevice"), marker.get("rootInode"))
        != (root.st_dev, root.st_ino)
        or not linux_crypto.supported()
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    target = Path("/work/installed")
    if sys.argv[1:] == ["--install-cut"]:
        real_run = linux_crypto.run
        reviews = []

        def approve_cut(summary):
            reviews.append(summary)
            Path("/work/reviews.json").write_text(json.dumps(reviews))
            return True

        def cut_after_apt(installation, name, *arguments):
            result = real_run(installation, name, *arguments)
            if name == "apt-get" and "--no-download" in arguments:
                os._exit(79)  # Explicit fixture cut after real APT, before journal ACK.
            return result

        linux_crypto.run = cut_after_apt
        linux_crypto.configure(target, review=approve_cut)
        raise ValueError("E_TEST_CUT_NOT_REACHED")
    if sys.argv[1:]:
        raise ValueError("E_TEST_ARGUMENTS")
    if any(Path("/usr/bin", name).exists() for name in ("gpg", "gpgconf")):
        raise ValueError("E_TEST_NOT_CLEAN")
    if target.exists():
        raise ValueError("E_TEST_TARGET_EXISTS")
    Installation(
        target,
        {"release": "1.0.0", "architecture": "linux/amd64"},
        "a" * 64,
        "fixture.test",
        "10.231.0.1",
    )
    with Path("/work/private-installer-cut.log").open("xb") as output:
        interrupted = subprocess.run(
            [sys.executable, __file__, "--install-cut"],
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=1200,
            check=False,
        )
    if (
        interrupted.returncode != 79
        or load_installation(target).state["cryptoPrerequisite"]["phase"]
        != "installing"
    ):
        raise ValueError("E_TEST_PACKAGE_CUT")
    reviews = json.loads(Path("/work/reviews.json").read_bytes())
    # Resume the exact reviewed versions without a fresh identity/implicit plan.
    result = linux_crypto.configure(target, review=lambda _: False)
    state = load_installation(target).state["cryptoPrerequisite"]
    if (
        not result["available"]
        or not result["packagesChanged"]
        or state["phase"] != "complete"
        or len(reviews) != 2
    ):
        raise ValueError("E_TEST_PACKAGE_INSTALLATION")
    plain = target / "synthetic.txt"
    plain.write_bytes(b"Synthetic developer fixture; no household/account data.\n")
    encrypted, restored = target / "synthetic.gpg", target / "restored.txt"
    password = "Synthetic-crypto-fixture-only-2026"
    crypto(plain, encrypted, password)
    crypto(encrypted, restored, password, decrypt=True)
    if plain.read_bytes() != restored.read_bytes():
        raise ValueError("E_TEST_CRYPTO_ROUNDTRIP")
    repeated = linux_crypto.configure(target, review=lambda _: False)
    if not repeated["available"] or repeated["packagesChanged"]:
        raise ValueError("E_TEST_PACKAGE_REPEAT")
    report = {
        "actualDebian13Chroot": True,
        "actualInitiallyMissingGnuPG": True,
        "actualAptMetadataRefresh": True,
        "actualReviewedPinnedPackageInstall": True,
        "actualEncryptedSyntheticRoundtrip": True,
        "actualRepeatWithoutPackageChanges": True,
        "packages": state["packages"],
        "systemBootAccepted": False,
        "applicationBackupRestoreAccepted": False,
        "interruptedPackageInstallAccepted": False,
        "actualInterruptedPackageAcknowledgementResumed": True,
        "installerCutPointInjected": "after-real-apt-before-journal-acknowledgement",
    }
    Path("/work/report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
