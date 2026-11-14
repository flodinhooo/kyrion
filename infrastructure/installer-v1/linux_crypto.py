"""Interactive Debian crypto prerequisite; never called by background workers."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from authority import require_active
from host import linux_release, reject_links
from recovery import load_installation
from runtime import installation_lock

NAME = re.compile(r"[a-z0-9][a-z0-9+.-]{0,100}(?::(?:amd64|arm64|all))?\Z")
VERSION = re.compile(r"[0-9][A-Za-z0-9.+:~_-]{0,150}\Z")
PHASES = {"metadata", "planned", "downloaded", "installing", "complete"}
OPTIONS = [
    "--no-install-recommends",
    "--no-remove",
    "--no-upgrade",
    "-o",
    "APT::Get::AllowUnauthenticated=false",
    "-o",
    "Acquire::AllowInsecureRepositories=false",
    "-o",
    "Acquire::AllowDowngradeToInsecureRepositories=false",
]


def executable(name: str) -> Path:
    if name not in {
        "gpg",
        "gpgconf",
        "gpg-agent",
        "apt-get",
        "apt-cache",
        "dpkg-query",
        "dpkg",
    }:
        raise ValueError("E_CRYPTO_PACKAGE_TOOL")
    path = Path("/usr/bin") / name
    reject_links(path)
    for item in (path, *path.parents):
        if item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
            raise ValueError("E_CRYPTO_PACKAGE_OWNER")
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("E_CRYPTO_PACKAGE_TOOL")
    return path


def run(installation, name: str, *arguments: str) -> str:
    program = executable(name)
    # Repository errors can contain credentials: never send raw output to UI,
    # the journal or diagnostics. Only strict metadata parsers consume it.
    with tempfile.TemporaryFile(dir=installation.target) as output:
        try:
            result = subprocess.run(
                [str(program), *arguments],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                cwd=installation.target,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": "/root",
                    "LC_ALL": "C",
                    "DEBIAN_FRONTEND": "noninteractive",
                },
                timeout=60 if name != "apt-get" or "--simulate" in arguments else 1800,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ValueError("E_CRYPTO_PACKAGE_INTERRUPTED") from None
        if result.returncode:
            raise ValueError("E_CRYPTO_PACKAGE_OPERATION")
        output.seek(0)
        raw = output.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2:
        raise ValueError("E_CRYPTO_PACKAGE_PLAN")
    return raw.decode("utf-8", errors="strict")


def available(installation) -> bool:
    if not all(
        (Path("/usr/bin") / name).is_file() for name in ("gpg", "gpgconf", "gpg-agent")
    ):
        return False
    return all(
        "GnuPG" in run(installation, name, "--version")
        for name in ("gpg", "gpgconf", "gpg-agent")
    )


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


def require_complete(state: dict) -> None:
    saved = state.get("cryptoPrerequisite")
    if saved is not None:
        validate(saved)
        if saved["phase"] != "complete":
            raise ValueError("E_CRYPTO_PACKAGE_REPAIR")


def pending(installation) -> set[str]:
    raw = run(
        installation, "dpkg-query", "-W", "-f=${binary:Package}\t${db:Status-Status}\n"
    )
    result = set()
    for line in raw.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or not NAME.fullmatch(fields[0]):
            raise ValueError("E_CRYPTO_PACKAGE_PLAN")
        if fields[1] not in {"installed", "not-installed", "config-files"}:
            result.add(fields[0])
    return result


def plan_rows(raw: str) -> list[dict]:
    result = []
    for line in raw.splitlines():
        if line.startswith("Remv "):
            raise ValueError("E_CRYPTO_PACKAGE_PLAN")
        if not line.startswith("Inst "):
            continue
        match = re.fullmatch(r"Inst (\S+) \((\S+) .+\)", line)
        if (
            match is None
            or not NAME.fullmatch(match[1])
            or not VERSION.fullmatch(match[2])
        ):
            # Existing-version [brackets] denote an upgrade. Do not turn this
            # optional prerequisite into an unreviewed OS/package replacement.
            raise ValueError("E_CRYPTO_PACKAGE_PLAN")
        result.append({"name": match[1], "version": match[2]})
    if len(result) > 128 or len({row["name"] for row in result}) != len(result):
        raise ValueError("E_CRYPTO_PACKAGE_PLAN")
    return result


def validate(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"formatVersion", "phase", "packages"}
        or type(value["formatVersion"]) is not int
        or value["formatVersion"] != 1
        or not isinstance(value["phase"], str)
        or value["phase"] not in PHASES
        or not isinstance(value["packages"], list)
        or len(value["packages"]) > 128
    ):
        raise ValueError("E_CRYPTO_PACKAGE_PLAN")
    names = set()
    for row in value["packages"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"name", "version"}
            or not isinstance(row["name"], str)
            or not NAME.fullmatch(row["name"])
            or not isinstance(row["version"], str)
            or not VERSION.fullmatch(row["version"])
            or row["name"] in names
        ):
            raise ValueError("E_CRYPTO_PACKAGE_PLAN")
        names.add(row["name"])
    if (
        (value["phase"] == "metadata" and names)
        or (value["phase"] != "metadata" and not names)
        or (names and "gnupg" not in {name.split(":")[0] for name in names})
    ):
        raise ValueError("E_CRYPTO_PACKAGE_PLAN")


def sizes(installation, packages: list[dict]) -> dict:
    download = expanded = 0
    for row in packages:
        raw = run(
            installation,
            "apt-cache",
            "--no-all-versions",
            "show",
            row["name"] + "=" + row["version"],
        )
        fields = {}
        for line in raw.splitlines():
            if line and not line.startswith(" ") and ": " in line:
                key, value = line.split(": ", 1)
                if key in fields:
                    raise ValueError("E_CRYPTO_PACKAGE_PLAN")
                fields[key] = value
        if (
            fields.get("Package") != row["name"].split(":")[0]
            or fields.get("Version") != row["version"]
            or any(
                not fields.get(key, "").isdigit() or not 0 < int(fields[key]) <= 1024**3
                for key in ("Size", "Installed-Size")
            )
        ):
            raise ValueError("E_CRYPTO_PACKAGE_PLAN")
        download += int(fields["Size"])
        expanded += int(fields["Installed-Size"]) * 1024
    return {"maximumDownloadBytes": download, "packageInstalledBytes": expanded}


def supported() -> bool:
    fields = linux_release()
    return (
        os.name == "posix"
        and platform.machine().lower() in {"x86_64", "aarch64"}
        and fields.get("ID", "").strip('"') == "debian"
        and fields.get("VERSION_ID", "").strip('"') == "13"
    )


def configure(target: Path, *, review) -> dict:
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    if not supported():
        raise ValueError("E_CRYPTO_PACKAGE_PLATFORM")
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        if installation.state.get("stage") == "uninstalled":
            raise ValueError("E_AUTHORITY_INACTIVE")
        installation.verify_files()
        saved = installation.state.get("cryptoPrerequisite")
        if saved is not None:
            validate(saved)
        if (saved is None or saved["phase"] == "complete") and available(installation):
            return {"available": True, "packagesChanged": False}
        if saved is None:
            if pending(installation):
                raise ValueError("E_CRYPTO_PACKAGE_REPAIR")
            if not review(
                {
                    "step": "metadata",
                    "package": "gnupg",
                    "repositoriesChanged": False,
                    "metadataBytes": None,
                }
            ):
                return {"available": False, "cancelled": True}
            saved = {"formatVersion": 1, "phase": "metadata", "packages": []}
            installation.state["cryptoPrerequisite"] = saved
            installation.save()
        if saved["phase"] == "complete":
            raise ValueError("E_CRYPTO_PACKAGE_REPAIR")
        if saved["phase"] == "metadata":
            run(installation, "apt-get", *OPTIONS, "update")
            packages = plan_rows(
                run(installation, "apt-get", *OPTIONS, "--simulate", "install", "gnupg")
            )
            if not packages or not any(
                row["name"].split(":")[0] == "gnupg" for row in packages
            ):
                raise ValueError("E_CRYPTO_PACKAGE_REPAIR")
            allocation = sizes(installation, packages)
            if not review(
                {
                    "step": "install",
                    "packages": packages,
                    **allocation,
                    "downloadsAuthenticatedByApt": True,
                    "existingPackagesUpgraded": False,
                }
            ):
                return {"available": False, "cancelled": True}
            saved.update(phase="planned", packages=packages)
            installation.save()
        packages = saved["packages"]
        allocation = sizes(installation, packages)
        if (
            shutil.disk_usage(Path("/var/cache/apt")).free
            < sum(allocation.values()) + 1024**3
        ):
            raise ValueError("E_DOWNLOAD_DISK")
        pinned = [row["name"] + "=" + row["version"] for row in packages]
        unfinished = pending(installation)
        if unfinished:
            names = {row["name"].split(":")[0] for row in packages}
            if saved["phase"] != "installing" or any(
                name.split(":")[0] not in names for name in unfinished
            ):
                raise ValueError("E_CRYPTO_PACKAGE_REPAIR")
            # Only our explicitly reviewed unfinished packages, never --pending.
            run(installation, "dpkg", "--configure", *sorted(unfinished))
        current = plan_rows(
            run(installation, "apt-get", *OPTIONS, "--simulate", "install", *pinned)
        )
        if any(row not in packages for row in current):
            raise ValueError("E_CRYPTO_PACKAGE_PLAN")
        # Reuse APT's verified cache, or replenish removed/incomplete archives
        # for the same reviewed versions. Never silently choose new versions.
        run(
            installation,
            "apt-get",
            *OPTIONS,
            "--yes",
            "--download-only",
            "install",
            *pinned,
        )
        if saved["phase"] == "planned":
            saved["phase"] = "downloaded"
            installation.save()
        current = plan_rows(
            run(installation, "apt-get", *OPTIONS, "--simulate", "install", *pinned)
        )
        if any(row not in packages for row in current):
            raise ValueError("E_CRYPTO_PACKAGE_PLAN")
        saved["phase"] = "installing"
        installation.save()
        run(
            installation,
            "apt-get",
            *OPTIONS,
            "--yes",
            "--no-download",
            "install",
            *pinned,
        )
        if not available(installation):
            raise ValueError("E_CRYPTO_PACKAGE_TOOL")
        saved["phase"] = "complete"
        installation.save()
        return {"available": True, "packagesChanged": True}


def interactive(target: Path, messages: dict[str, str]) -> dict:
    def review(summary):
        print(messages["cryptoPackageReview"])
        print(json.dumps(summary, ensure_ascii=True))
        expected = (
            "REFRESH-METADATA" if summary["step"] == "metadata" else "INSTALL-CRYPTO"
        )
        return input("[" + expected + "/CANCEL]: ").strip() == expected

    return configure(target, review=review)
