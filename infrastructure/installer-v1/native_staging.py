"""Immutable private native release inputs after review; no mutable download paths."""

from __future__ import annotations

import hashlib
import secrets
import shutil
from pathlib import Path

from bundle import ReviewedBundle, sha256, verify_signature
from crypto_support import verify_ed25519
from host import reject_links
from native_bundle import MAXIMUM_MANIFEST
from runtime import Installation, copy_image_input


def stage_bundle(
    installation: Installation, source: Path, key: Path, reviewed: ReviewedBundle
) -> Path:
    root = installation.target / "release-input"
    reject_links(root)
    state = installation.state.get("nativeArchive")
    if state is None:
        if root.exists():
            raise ValueError("E_NATIVE_STAGING_UNOWNED")
        state = {
            "formatVersion": 1,
            "manifestSha256": reviewed.manifest_sha256,
            "pending": None,
            "preserved": [],
        }
        installation.state["nativeArchive"] = state
        installation.save()
    if (
        not isinstance(state, dict)
        or set(state) != {"formatVersion", "manifestSha256", "pending", "preserved"}
        or type(state["formatVersion"]) is not int
        or state["formatVersion"] != 1
        or state["manifestSha256"] != reviewed.manifest_sha256
        or not isinstance(state["preserved"], list)
        or len(state["preserved"]) > 128
    ):
        raise ValueError("E_NATIVE_STAGING_STATE")
    import re

    def partial(value):
        return isinstance(value, str) and re.fullmatch(
            r"\.native-archive-[a-f0-9]{32}", value
        )

    if (
        not all(partial(value) for value in state["preserved"])
        or len(set(state["preserved"])) != len(state["preserved"])
        or state["pending"] is not None
        and not partial(state["pending"])
    ):
        raise ValueError("E_NATIVE_STAGING_STATE")
    root.mkdir(mode=0o700, exist_ok=True)
    item = reviewed.manifest["artifact"]
    archive = root / item["name"]
    allowed = {
        "manifest.json",
        "manifest.sig",
        "public.pem",
        item["name"],
        *state["preserved"],
    }
    if state["pending"]:
        allowed.add(state["pending"])
    for child in root.iterdir():
        reject_links(child)
        if not child.is_file() or child.name not in allowed:
            raise ValueError("E_NATIVE_STAGING_UNOWNED")
    if state["pending"] and (root / state["pending"]).exists():
        if len(state["preserved"]) >= 128:
            raise ValueError("E_NATIVE_STAGING_PARTIALS")
        state["preserved"].append(state["pending"])
    state["pending"] = None
    installation.save()
    raw = verify_signature(source, key, MAXIMUM_MANIFEST)
    if hashlib.sha256(raw).hexdigest() != reviewed.manifest_sha256:
        raise ValueError("E_REVIEW_CHANGED")
    with (source / "manifest.sig").open("rb") as stream:
        signature = stream.read(1025)
    with key.open("rb") as stream:
        public = stream.read(16385)
    if len(signature) > 1024 or len(public) > 16384:
        raise ValueError("E_SIGNATURE")
    verify_ed25519(raw, signature, public)
    for name, payload in (
        ("manifest.json", raw),
        ("manifest.sig", signature),
        ("public.pem", public),
    ):
        installation.write("release-input/" + name, payload)
    if archive.exists():
        if archive.stat().st_size != item["bytes"] or sha256(archive) != item["sha256"]:
            raise ValueError("E_NATIVE_STAGING_CHANGED")
        return root
    required = (
        item["bytes"]
        + sum(row["bytes"] for row in reviewed.manifest["files"])
        + 12 * 1024**3
    )
    if shutil.disk_usage(installation.target).free < required:
        raise ValueError("E_NATIVE_DISK")
    temporary = ".native-archive-" + secrets.token_hex(16)
    state["pending"] = temporary
    installation.save()
    copy_image_input(source / item["name"], root / temporary, item)
    (root / temporary).rename(archive)
    state["pending"] = None
    installation.save()
    return root
