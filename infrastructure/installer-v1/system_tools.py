"""Fixed read-only OS tool discovery, never a caller PATH or executable alias."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import IO, TypedDict, Unpack


class RunOptions(TypedDict, total=False):
    stdin: int | IO[bytes] | None
    stdout: int | IO[bytes] | None
    stderr: int | IO[bytes] | None
    input: bytes | str
    capture_output: bool
    text: bool
    timeout: int | float
    check: bool
    cwd: str | Path


def executable(name: str) -> Path | None:
    if os.name == "nt":
        from windows_system import system_directory

        paths = {"nvidia-smi": (system_directory() / "nvidia-smi.exe",)}.get(name, ())
    else:
        paths = {
            "docker": (Path("/usr/bin/docker"),),
            "systemctl": (Path("/usr/bin/systemctl"),),
            "lsusb": (Path("/usr/bin/lsusb"),),
            "openssl": (Path("/usr/bin/openssl"),),
            "gpg": (Path("/usr/bin/gpg"),),
            "gpgconf": (Path("/usr/bin/gpgconf"),),
            "gpg-agent": (Path("/usr/bin/gpg-agent"),),
            "nvidia-smi": (
                Path("/usr/bin/nvidia-smi"),
                Path("/usr/lib/wsl/lib/nvidia-smi"),
            ),
        }.get(name, ())
    for path in paths:
        try:
            if not path.is_file():
                continue
            if os.name == "nt":
                from host import reject_links

                reject_links(path)
                return path
            resolved = path.resolve(strict=True)
            if path.lstat().st_uid != 0 or not os.access(resolved, os.X_OK):
                continue
            if any(
                item.stat().st_uid != 0 or item.stat().st_mode & 0o022
                for item in (resolved, *resolved.parents, *path.parents)
            ):
                continue
            return resolved
        except (OSError, ValueError):
            continue
    return None


def environment() -> dict[str, str]:
    if os.name == "nt":
        from windows_system import base_environment

        return base_environment()
    return {"PATH": "/usr/bin:/bin", "HOME": "/root", "LANG": "C", "LC_ALL": "C"}


def required(name: str) -> Path:
    selected = executable(name)
    if selected is None:
        raise ValueError("E_SYSTEM_TOOL")
    return selected


def run(
    arguments: list[str], **options: Unpack[RunOptions]
) -> subprocess.CompletedProcess:
    if not arguments:
        raise ValueError("E_SYSTEM_TOOL")
    command = [str(required(arguments[0])), *arguments[1:]]
    if "stdin" not in options and "input" not in options:
        options["stdin"] = subprocess.DEVNULL
    check = options.pop("check", False)
    return subprocess.run(
        command,
        env=environment(),
        check=check,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        **options,
    )
