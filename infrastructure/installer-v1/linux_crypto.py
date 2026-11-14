"""GnuPG-specific guided prerequisite over the shared Debian package operation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import linux_packages as packages
from linux_packages import PHASES, plan_rows, require_complete, run, supported, validate
from recovery import load_installation
from runtime import installation_lock

__all__ = [
    "PHASES",
    "available",
    "configure",
    "interactive",
    "needs_configuration",
    "plan_rows",
    "require_available",
    "require_complete",
    "run",
    "supported",
    "validate",
]


def available(installation) -> bool:
    if not all(
        (Path("/usr/bin") / name).is_file() for name in ("gpg", "gpgconf", "gpg-agent")
    ):
        return False
    return all(
        "GnuPG" in run(installation, name, "--version")
        for name in ("gpg", "gpgconf", "gpg-agent")
    )


def require_available(installation) -> None:
    require_complete(installation.state)
    if os.name == "posix" and not available(installation):
        raise ValueError("E_GPG_REQUIRED")


def needs_configuration(target: Path) -> bool:
    if os.name != "posix":
        return False
    with installation_lock(target):
        saved = load_installation(target).state.get("cryptoPrerequisite")
        if saved is not None:
            validate(saved)
            if saved["phase"] != "complete":
                return True
    return not all(
        (Path("/usr/bin") / name).is_file() for name in ("gpg", "gpgconf", "gpg-agent")
    )


def configure(target: Path, *, review, restore_request: dict | None = None) -> dict:
    return packages.configure(
        target,
        spec=packages.CRYPTO,
        ready=available,
        review=review,
        restore_request=restore_request,
    )


def interactive(target: Path, messages: dict[str, str]) -> dict:
    def review(summary):
        print(messages["cryptoPackageReview"])
        print(json.dumps(summary, ensure_ascii=True))
        expected = (
            "REFRESH-METADATA" if summary["step"] == "metadata" else "INSTALL-CRYPTO"
        )
        return input("[" + expected + "/CANCEL]: ").strip() == expected

    return configure(target, review=review)
