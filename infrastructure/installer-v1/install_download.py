"""Fresh-install acquisition using the build-bound signed release channel."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import backup_store
from build_identity import read_build
from bundle import unique_object
from host import reject_links
from release_channel import embedded
from release_policy import fetch_document, fresh_release, verify
from runtime import installation_lock
from update_download import (
    artifact_plan,
    manifest_bytes,
    stream_artifact,
    validate_payload,
)

PROOF = "release-index.json"
SCHEMA = 49
API = 1


def interactive(target: Path, platform: str, messages: dict[str, str]):
    def review(summary):
        print(messages["installDownloadReview"])
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return input(messages["approve"] + " [DOWNLOAD]: ").strip() == "DOWNLOAD"

    last_progress = 0.0

    def progress(name, done, total):
        nonlocal last_progress
        current = time.monotonic()
        if done == total or current - last_progress >= 1:
            print(
                messages["installDownloadProgress"].format(
                    name=name, done=done, total=total
                ),
                flush=True,
            )
            last_progress = current

    return prepare(target, platform, review=review, progress=progress)


def bounded(path: Path, limit: int) -> bytes:
    reject_links(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= limit:
        raise ValueError("E_INSTALL_DOWNLOAD_PROOF")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("E_INSTALL_DOWNLOAD_PROOF")
    return raw


def candidate(proof: bytes, platform: str) -> dict:
    channel = embedded()
    if channel is None:
        raise ValueError("E_INSTALLER_CHANNEL_REQUIRED")
    index = verify(proof, channel["trust"], "release-index")
    selected = fresh_release(index, read_build()["version"], platform, SCHEMA, API)
    if selected is None:
        raise ValueError("E_INSTALL_DOWNLOAD_COMPATIBILITY")
    return selected


@dataclass(frozen=True)
class IndexAuthority:
    manifest_sha256: str
    platform: str

    def manifest(self, root: Path, maximum: int) -> bytes:
        selected = candidate(bounded(root / PROOF, 1024**2), self.platform)
        raw = bounded(root / "manifest.json", maximum)
        if (
            selected["manifestSha256"] != self.manifest_sha256
            or hashlib.sha256(raw).hexdigest() != self.manifest_sha256
        ):
            raise ValueError("E_INSTALL_DOWNLOAD_PROOF")
        artifact_plan(raw, selected)
        return raw


def prepare(
    target: Path, platform: str, *, review, progress=None
) -> tuple[Path, IndexAuthority]:
    """No installation mutation. Review precedes cache creation/large downloads."""
    from operational_restore import require_admin

    require_admin()
    target = target.absolute()
    reject_links(target)
    root = target.parent / ("." + target.name + ".release-download")
    reject_links(root)
    channel = embedded()
    if channel is None:
        raise ValueError("E_INSTALLER_CHANNEL_REQUIRED")
    marker = {
        "formatVersion": 1,
        "kind": "kyrion-install-download",
        "target": str(target.resolve()),
    }
    with installation_lock(root):
        existing = root.exists()
        if existing:
            backup_store.secure_directory(root)
            saved = json.loads(
                bounded(root / "owner.json", 16384), object_pairs_hook=unique_object
            )
            if saved != marker:
                raise ValueError("E_INSTALL_DOWNLOAD_OWNER")
            # Continue the exact authorized release, including offline; no quiet
            # selection of a different release after a partial installation.
            proof = bounded(root / PROOF, 1024**2)
            raw = bounded(root / "manifest.json", 8 * 1024**2)
        else:
            proof = fetch_document(channel["feed"])
            selected = candidate(proof, platform)
            raw = manifest_bytes(selected["manifestUrl"])
        selected = candidate(proof, platform)
        items = artifact_plan(raw, selected)
        manifest = json.loads(raw, object_pairs_hook=unique_object)
        expanded = 0
        licenses = None
        if platform == "windows/amd64":
            rows = manifest.get("files")
            if (
                not isinstance(rows, list)
                or not 1 <= len(rows) <= 20000
                or any(
                    not isinstance(row, dict)
                    or type(row.get("bytes")) is not int
                    or not 0 <= row["bytes"] <= 1024**3
                    for row in rows
                )
            ):
                raise ValueError("E_NATIVE_FILES")
            expanded = sum(row["bytes"] for row in rows)
            if expanded > 12 * 1024**3:
                raise ValueError("E_NATIVE_FILES")
            licenses = {
                name: {
                    field: component.get(field)
                    for field in ("license", "licenseUrl", "sourceUrl")
                }
                for name, component in manifest["components"].items()
            }
        allowed = {"owner.json", PROOF, "manifest.json"}
        allowed.update(item["name"] for item in items)
        allowed.update("artifact-" + str(i) + ".partial" for i in range(len(items)))
        if existing:
            for child in root.iterdir():
                reject_links(child)
                if not child.is_file() or child.name not in allowed:
                    raise ValueError("E_INSTALL_DOWNLOAD_OWNER")
        summary = {
            "release": selected["version"],
            "platform": platform,
            "components": selected["components"],
            "artifactBytes": sum(item["bytes"] for item in items),
            "releaseNotes": selected["notesUrl"],
            "target": str(target),
            "cache": str(root),
            "systemChangesApprovedSeparately": True,
            "resuming": existing,
            "expandedBytes": expanded if platform == "windows/amd64" else None,
            "componentLicenses": licenses,
        }
        if not review(summary):
            raise ValueError("E_INSTALL_DOWNLOAD_CANCELLED")
        remaining = 0
        for position, item in enumerate(items):
            complete = root / item["name"]
            partial = root / ("artifact-" + str(position) + ".partial")
            reject_links(complete)
            reject_links(partial)
            present = (
                complete.stat().st_size
                if complete.is_file()
                else partial.stat().st_size
                if partial.is_file()
                else 0
            )
            remaining += max(0, item["bytes"] - min(item["bytes"], present))
        # Reserve the private installation copy and baseline operating space too.
        if (
            shutil.disk_usage(target.parent).free
            < remaining + summary["artifactBytes"] + expanded + 12 * 1024**3
        ):
            raise ValueError("E_DOWNLOAD_DISK")
        if not existing:
            # Only publish a complete metadata set. Interrupted preparation
            # remains a private unadopted sibling, never a half-owned cache.
            staging = root.with_name(root.name + ".preparing-" + uuid.uuid4().hex)
            backup_store.create_directory(staging)
            for name, payload in (
                ("owner.json", json.dumps(marker, sort_keys=True).encode()),
                (PROOF, proof),
                ("manifest.json", raw),
            ):
                backup_store.publish(staging / name, payload, staging)
            reject_links(root)
            if root.exists():
                raise ValueError("E_INSTALL_DOWNLOAD_OWNER")
            staging.rename(root)
            if os.name == "posix":
                descriptor = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        for position, item in enumerate(items):
            stream_artifact(
                urljoin(selected["manifestUrl"], item["name"]),
                root / item["name"],
                root / ("artifact-" + str(position) + ".partial"),
                item,
                security_source=root,
                progress=(
                    lambda done, total, name=item["name"]: progress(name, done, total)
                )
                if progress is not None
                else None,
            )
        authority = IndexAuthority(selected["manifestSha256"], platform)
        authority.manifest(root, 8 * 1024**2)
        validate_payload(root, raw, selected)
        return root, authority
