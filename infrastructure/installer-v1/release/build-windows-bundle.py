"""Build an unsigned native Windows runtime bundle from a clean public profile.

No runtime download, machine installation or publication occurs here. Source
assembly and runtime/OS acceptance are distinct release-pipeline stages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bundle import sha256, unique_object
from host import reject_links
from native_bundle import MAXIMUM_EXPANDED, MAXIMUM_MANIFEST, safe_member, validate


def build(profile: Path, metadata: dict, output: Path) -> dict:
    reject_links(profile)
    reject_links(output)
    if (
        not profile.is_dir()
        or output.exists()
        or not output.parent.is_dir()
        or output.resolve().is_relative_to(profile.resolve())
        or not isinstance(metadata, dict)
        or set(metadata) != {"release", "components", "compatibility"}
    ):
        raise ValueError("E_NATIVE_BUILD_INPUT")
    sources = []
    total = 0
    for path in sorted(profile.rglob("*")):
        reject_links(path)
        if path.is_dir():
            continue
        name = safe_member(path.relative_to(profile).as_posix())
        if not path.is_file() or path.stat().st_size > 1024**3:
            raise ValueError("E_NATIVE_BUILD_FILE")
        total += path.stat().st_size
        if total > MAXIMUM_EXPANDED or len(sources) >= 20000:
            raise ValueError("E_NATIVE_BUILD_SIZE")
        sources.append((name, path))
    with tempfile.TemporaryDirectory(
        prefix=".native-release-", dir=output.parent
    ) as directory:
        temporary = Path(directory)
        archive_path = temporary / "kyrion-windows-amd64.zip"
        files = []
        with zipfile.ZipFile(
            archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for name, path in sources:
                files.append(
                    {"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)}
                )
                archive.write(path, name)
        manifest = {
            "schemaVersion": 3,
            "runtime": "windows-native",
            "architecture": "windows/amd64",
            **metadata,
            "artifact": {
                "name": archive_path.name,
                "bytes": archive_path.stat().st_size,
                "sha256": sha256(archive_path),
            },
            "files": files,
        }
        raw = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
        if len(raw) > MAXIMUM_MANIFEST:
            raise ValueError("E_NATIVE_MANIFEST_SIZE")
        (temporary / "manifest.json").write_bytes(raw)
        # Hash actual archive contents again: an input changed during build must
        # fail rather than generate a signable manifest with stale file hashes.
        validate(temporary)
        output.mkdir(mode=0o700)
        for name in (archive_path.name, "manifest.json"):
            source = temporary / name
            destination = output / name
            with source.open("rb") as incoming, destination.open("xb") as outgoing:
                while chunk := incoming.read(1024**2):
                    outgoing.write(chunk)
                outgoing.flush()
                os.fsync(outgoing.fileno())
        return {
            "schemaVersion": 3,
            "release": manifest["release"],
            "architecture": "windows/amd64",
            "manifestSha256": hashlib.sha256(raw).hexdigest(),
            "artifact": manifest["artifact"],
            "fileCount": len(files),
            "signed": False,
            "platformInstallationAccepted": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.metadata.stat().st_size > MAXIMUM_MANIFEST:
        raise SystemExit("E_NATIVE_BUILD_METADATA")
    print(
        json.dumps(
            build(
                arguments.profile,
                json.loads(
                    arguments.metadata.read_text(encoding="utf-8"),
                    object_pairs_hook=unique_object,
                ),
                arguments.output,
            )
        )
    )
