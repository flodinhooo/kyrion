"""Monotonic installer authority retirement, using the existing private journal."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import uuid
from pathlib import Path

from bundle import unique_object
from host import reject_links
from runtime import atomic_json

DOMAIN = b"kyrion-operational-authority-transfer-v1\x00"


def require_active(
    state: dict,
    *,
    preparing: bool = False,
    migration: bool = False,
    update: bool = False,
) -> None:
    if state.get("authority") is not None or (
        state.get("preparedForRestore")
        and not preparing
        and not (migration and state.get("restore", {}).get("phase") == "migrating")
    ):
        raise ValueError("E_AUTHORITY_INACTIVE")
    from update_gate import fenced

    if fenced(state) and not update:
        raise ValueError("E_UPDATE_IN_PROGRESS")


def prepare_restore(installation, request: dict) -> None:
    previous = installation.state.get("restoreRequest")
    if previous is None:
        if installation.state.get("stage") != "reviewed" or installation.state["files"]:
            raise ValueError("E_RESTORE_TARGET_NOT_EMPTY")
        installation.state["restoreRequest"] = request
        installation.state["preparedForRestore"] = True
        installation.save()
    elif (
        previous != request or installation.state.get("preparedForRestore") is not True
    ):
        raise ValueError("E_RESTORE_REQUEST_CONFLICT")


def binding(source: str, target: str, digest: str) -> dict:
    try:
        source, target = str(uuid.UUID(source)), str(uuid.UUID(target))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("E_AUTHORITY_TRANSFER") from None
    if (
        source == target
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
    ):
        raise ValueError("E_AUTHORITY_TRANSFER")
    return {
        "formatVersion": 1,
        "kind": "kyrion-authority-transfer",
        "sourceInstallationId": source,
        "targetInstallationId": target,
        "backupSha256": digest,
    }


def signature(document: dict, key: bytes) -> str:
    if len(key) != 32:
        raise ValueError("E_AUTHORITY_KEY")
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hmac.new(key, DOMAIN + raw, hashlib.sha256).hexdigest()


def retire(installation, target: str, digest: str, stop_owned) -> dict:
    """Caller holds the installation lock and authenticates host administration.

    stop_owned validates ownership and stops/disables the complete service set.
    No receipt is returned until it finishes successfully. A crash leaves intent
    in the same journal; ordinary provisioning/repair must refuse that state.
    """
    if (
        type(installation.state.get("authorityFenceVersion")) is not int
        or installation.state.get("authorityFenceVersion") != 1
    ):
        raise ValueError("E_AUTHORITY_UPGRADE_REQUIRED")
    document = binding(installation.state["installationId"], target, digest)
    previous = installation.state.get("authority")
    if previous is not None and (
        not isinstance(previous, dict)
        or set(previous) != {"phase", "transfer"}
        or previous["transfer"] != document
        or previous["phase"] not in {"retiring", "retired"}
    ):
        raise ValueError("E_AUTHORITY_TRANSFER_CONFLICT")
    key_path = installation.target / "secrets/audit-integrity.key"
    reject_links(key_path)
    if not key_path.is_file() or key_path.stat().st_size != 32:
        raise ValueError("E_AUTHORITY_KEY")
    key = key_path.read_bytes()
    installation.verify_files()
    if previous is None:
        installation.state["authority"] = {"phase": "retiring", "transfer": document}
        installation.state["authorityAudit"] = {
            "actorType": "HOST_ADMIN",
            "correlationId": document["targetInstallationId"],
            "startedAt": int(time.time()),
        }
        installation.save()
    # Repeat stop/disable even after a completed retirement; do not just trust
    # a historical success bit if the administrator changed service state.
    if "authorityAudit" not in installation.state:
        installation.state["authorityAudit"] = {
            "actorType": "HOST_ADMIN",
            "correlationId": document["targetInstallationId"],
            "startedAt": None,
        }
        installation.save()
    if (
        not isinstance(installation.state["authorityAudit"], dict)
        or installation.state["authorityAudit"].get("correlationId")
        != document["targetInstallationId"]
        or installation.state["authorityAudit"].get("actorType") != "HOST_ADMIN"
    ):
        raise ValueError("E_AUTHORITY_TRANSFER_CONFLICT")
    stop_owned(installation)
    installation.state["authority"] = {"phase": "retired", "transfer": document}
    now = int(time.time())
    installation.state["authorityAudit"].setdefault(
        "completedAt", None if previous and previous["phase"] == "retired" else now
    )
    installation.state["authorityAudit"]["verifiedAt"] = now
    installation.save()
    return {"transfer": document, "authentication": signature(document, key)}


def verify_receipt(
    raw: bytes, source: str, target: str, digest: str, key: bytes
) -> dict:
    if len(raw) > 4096:
        raise ValueError("E_AUTHORITY_RECEIPT")
    try:
        value = json.loads(raw, object_pairs_hook=unique_object)
        expected = binding(source, target, digest)
        if (
            not isinstance(value, dict)
            or set(value) != {"transfer", "authentication"}
            or not isinstance(value["transfer"], dict)
            or type(value["transfer"].get("formatVersion")) is not int
            or value["transfer"] != expected
            or not isinstance(value["authentication"], str)
            or not hmac.compare_digest(
                value["authentication"], signature(expected, key)
            )
        ):
            raise ValueError("E_AUTHORITY_RECEIPT")
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ValueError("E_AUTHORITY_RECEIPT") from None
    return expected


def export_receipt(path: Path, receipt: dict) -> None:
    reject_links(path)
    if path.exists() or not path.parent.is_dir():
        raise ValueError("E_EXISTING_STATE")
    # Receipt contains no secret. Never overwrite an earlier transfer artifact.
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    try:
        atomic_json(temporary, receipt)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
