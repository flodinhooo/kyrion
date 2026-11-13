"""Embedded installer build identity; never assume a source checkout is released."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bundle import VERSION, unique_object
from host import reject_links

DEVELOPMENT_VERSION = "0.0.0-dev.0"


def read_build(root: Path | None = None, frozen: bool | None = None) -> dict:
    root = root if root is not None else Path(__file__).resolve().parent
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    path = root / "installer-build.json"
    try:
        reject_links(path)
    except ValueError:
        raise ValueError("E_INSTALLER_BUILD") from None
    if not path.exists():
        if frozen:
            raise ValueError("E_INSTALLER_BUILD")
        return {"formatVersion": 1, "version": DEVELOPMENT_VERSION}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError("E_INSTALLER_BUILD")
    try:
        result = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError):
        raise ValueError("E_INSTALLER_BUILD") from None
    if (
        not isinstance(result, dict)
        or set(result)
        not in (
            {"formatVersion", "version"},
            {"formatVersion", "version", "releaseChannelSha256"},
        )
        or type(result["formatVersion"]) is not int
        or result["formatVersion"] != 1
        or not isinstance(result["version"], str)
        or not VERSION.fullmatch(result["version"])
        or "latest" in result["version"].lower()
    ):
        raise ValueError("E_INSTALLER_BUILD")
    if "releaseChannelSha256" in result and (
        not isinstance(result["releaseChannelSha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", result["releaseChannelSha256"])
    ):
        raise ValueError("E_INSTALLER_BUILD")
    return result
