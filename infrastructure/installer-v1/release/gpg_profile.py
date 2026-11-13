"""Validate prepared public GnuPG inputs before copying them into a release."""

from __future__ import annotations

import json
from pathlib import Path

from bundle import sha256, unique_object
from host import reject_links
from native_bundle import safe_member


def verify_profile(root: Path) -> dict:
    reject_links(root)
    document = root / "vendor.json"
    reject_links(document)
    if not document.is_file() or document.stat().st_size > 1024**2:
        raise ValueError("E_GPG_PROFILE")
    metadata = json.loads(document.read_bytes(), object_pairs_hook=unique_object)
    lock = json.loads(
        Path(__file__).with_name("gnupg-windows-lock.json").read_bytes(),
        object_pairs_hook=unique_object,
    )
    if (
        not isinstance(metadata, dict)
        or type(metadata.get("formatVersion")) is not int
        or metadata.get("formatVersion") != 1
        or metadata.get("kind") != "kyrion-portable-gnupg"
        or metadata.get("version") != lock["version"]
        or metadata.get("sourceSha256") != lock["sources"]["archive"]["sha256"]
        or metadata.get("sourceUrl") != lock["sources"]["archive"]["url"]
        or metadata.get("verifiedPrimaryFingerprint") != lock["primaryFingerprint"]
        or metadata.get("vendorSignatureVerified") is not True
        or metadata.get("correspondingSourceSignatureVerified") is not True
        or not isinstance(metadata.get("files"), dict)
        or not 4 <= len(metadata["files"]) <= 1000
    ):
        raise ValueError("E_GPG_PROFILE")
    required = {
        "bin/gpg.exe",
        "bin/gpgconf.exe",
        "bin/gpg-agent.exe",
        "bin/gpgconf.ctl",
        "README.txt",
    }
    if not required <= metadata["files"].keys():
        raise ValueError("E_GPG_PROFILE")
    for kind in ("sourceArchive", "sourceSignature", "keys"):
        source = lock["sources"][kind]
        if metadata["files"].get("share/kyrion-source/" + source["file"]) != {
            "bytes": source["bytes"],
            "sha256": source["sha256"],
        }:
            raise ValueError("E_GPG_PROFILE_SOURCE")
    if "share/kyrion-source/licenses/COPYING" not in metadata["files"]:
        raise ValueError("E_GPG_PROFILE_SOURCE")
    observed = set()
    for path in root.rglob("*"):
        reject_links(path)
        if path.is_dir():
            continue
        name = path.relative_to(root).as_posix()
        safe_member("runtime/installer/gnupg/" + name)
        if name == "vendor.json":
            continue
        if not name.startswith(("bin/", "share/")) and name != "README.txt":
            raise ValueError("E_GPG_PROFILE_CHANGED")
        expected = metadata["files"].get(name)
        if (
            not path.is_file()
            or not isinstance(expected, dict)
            or set(expected) != {"bytes", "sha256"}
            or type(expected["bytes"]) is not int
            or expected["bytes"] != path.stat().st_size
            or expected["sha256"] != sha256(path)
        ):
            raise ValueError("E_GPG_PROFILE_CHANGED")
        observed.add(name)
    if (
        observed != set(metadata["files"])
        or (root / "bin/gpgconf.ctl").read_bytes() != b""
    ):
        raise ValueError("E_GPG_PROFILE_CHANGED")
    return metadata
