#!/usr/bin/env python3
"""Strict, streaming validation of immutable release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

MAX_MANIFEST = 1024 * 1024
VERSION = re.compile(r"[0-9][0-9A-Za-z._-]{0,79}\Z")


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("E_MANIFEST: duplicate JSON field")
        result[key] = value
    return result


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(root: Path, manifest_path: Path) -> dict:
    if manifest_path.is_symlink() or manifest_path.stat().st_size > MAX_MANIFEST:
        raise ValueError("E_MANIFEST: invalid manifest file")
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )
    required = {"schemaVersion", "release", "architecture", "artifacts"}
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or type(manifest["schemaVersion"]) is not int
        or manifest["schemaVersion"] != 1
        or not isinstance(manifest["architecture"], str)
        or manifest["architecture"] not in {"linux/arm64", "linux/amd64"}
    ):
        raise ValueError("E_MANIFEST: unsupported or unknown manifest fields")
    version = manifest["release"]
    if (
        not isinstance(version, str)
        or not VERSION.fullmatch(version)
        or "latest" in version.lower()
    ):
        raise ValueError("E_RELEASE: immutable release version required")
    items = manifest["artifacts"]
    if not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise ValueError("E_ARTIFACTS: invalid artifact count")
    names = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"name", "sha256", "bytes"}:
            raise ValueError("E_ARTIFACT: malformed artifact")
        name = item["name"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.tar", name)
            or name in names
            or type(item["bytes"]) is not int
            or not 0 < item["bytes"] <= 64 * 1024**3
            or not isinstance(item["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        ):
            raise ValueError("E_ARTIFACT: invalid name, digest or size")
        names.add(name)
        path = root / name
        # Check before resolution: resolve() hides symlinks.
        if (
            path.is_symlink()
            or not path.is_file()
            or path.resolve().parent != root.resolve()
        ):
            raise ValueError("E_ARTIFACT: missing or unsafe artifact")
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError("E_DIGEST: artifact size or checksum mismatch")
    return manifest


def authenticate(root: Path, public_key: Path) -> dict:
    """Authenticate exact manifest bytes before interpreting artifact paths."""
    manifest = root / "manifest.json"
    signature = root / "manifest.sig"
    for path, limit in (
        (manifest, MAX_MANIFEST),
        (signature, 1024),
        (public_key, 16384),
    ):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError("E_SIGNATURE: missing or unsafe signature/trust material")
    try:
        result = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-rawin",
                "-pubin",
                "-inkey",
                str(public_key),
                "-sigfile",
                str(signature),
                "-in",
                str(manifest),
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("E_SIGNATURE: verifier unavailable") from error
    if result.returncode:
        raise ValueError("E_SIGNATURE: release authentication failed")
    return validate(root, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.root, args.manifest), sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
