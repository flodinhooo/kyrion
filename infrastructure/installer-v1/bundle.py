#!/usr/bin/env python3
"""Strict, streaming validation of immutable release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
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


def validate(
    root: Path, manifest_path: Path, authenticated_bytes: bytes | None = None
) -> dict:
    if manifest_path.is_symlink() or manifest_path.stat().st_size > MAX_MANIFEST:
        raise ValueError("E_MANIFEST: invalid manifest file")
    raw = (
        manifest_path.read_bytes()
        if authenticated_bytes is None
        else authenticated_bytes
    )
    if len(raw) > MAX_MANIFEST:
        raise ValueError("E_MANIFEST: invalid manifest size")
    manifest = json.loads(raw, object_pairs_hook=unique_object)
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


@dataclass(frozen=True)
class ReviewedBundle:
    manifest: dict
    manifest_sha256: str


def authenticated_review(root: Path, public_key: Path) -> ReviewedBundle:
    """Authenticate exact manifest bytes before interpreting artifact paths."""
    raw = verify_signature(root, public_key)
    return ReviewedBundle(
        validate(root, root / "manifest.json", raw), hashlib.sha256(raw).hexdigest()
    )


def authenticate(root: Path, public_key: Path) -> dict:
    return authenticated_review(root, public_key).manifest


def verify_signature(
    root: Path, public_key: Path, maximum: int = MAX_MANIFEST
) -> bytes:
    """Shared detached-signature boundary; each runtime validates its own schema."""
    manifest = root / "manifest.json"
    signature = root / "manifest.sig"
    snapshots = []
    for path, limit in (
        (manifest, maximum),
        (signature, 1024),
        (public_key, 16384),
    ):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError("E_SIGNATURE: missing or unsafe signature/trust material")
        with path.open("rb") as stream:
            value = stream.read(limit + 1)
        if len(value) > limit:
            raise ValueError("E_SIGNATURE: invalid signature/trust material size")
        snapshots.append(value)
    try:
        # Process the immutable bytes verified here, not a subsequent reopening
        # of downloaded metadata. Assets still require private caller staging.
        with tempfile.TemporaryDirectory(prefix="kyrion-manifest-") as directory:
            paths = [
                Path(directory) / name
                for name in ("manifest", "signature", "public.pem")
            ]
            for path, value in zip(paths, snapshots, strict=True):
                with os.fdopen(
                    os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
                ) as stream:
                    stream.write(value)
            result = subprocess.run(
                [
                    "openssl",
                    "pkeyutl",
                    "-verify",
                    "-rawin",
                    "-pubin",
                    "-inkey",
                    str(paths[2]),
                    "-sigfile",
                    str(paths[1]),
                    "-in",
                    str(paths[0]),
                ],
                capture_output=True,
                timeout=20,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("E_SIGNATURE: verifier unavailable") from error
    if result.returncode:
        raise ValueError("E_SIGNATURE: release authentication failed")
    return snapshots[0]


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
