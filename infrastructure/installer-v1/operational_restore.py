"""Guided two-phase restore using existing journals, runtimes and Core data."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path

from authority import export_receipt, retire, verify_receipt
from bundle import VERSION, sha256, unique_object
from host import reject_links
from portable_database import restore as restore_database
from recovery import COUNTS_SQL, load_installation, verified_plaintext
from restore_material import (
    extract_rows,
    private_output,
    read_member,
    reconcile_managed,
    replace_managed,
    restore_keys_and_data,
)
from restore_platform import backend
from runtime import installation_lock

SCHEMA_SQL = "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'"


def require_admin() -> None:
    if os.name == "nt":
        import ctypes

        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise ValueError("E_NATIVE_ELEVATION")
    elif os.name != "posix" or os.geteuid() != 0:
        raise ValueError("E_PLATFORM")


def plaintext_options(installation, platform) -> dict:
    return {
        "executable": platform.gpg,
        "environment": platform.environment,
        "private_parent": installation.target,
        "security_source": installation.path
        if installation.state.get("backend") == "windows-native"
        else None,
    }


def retire_source(
    target: Path,
    backup: Path,
    password: str,
    target_id: str,
    output: Path,
    review: Callable[[dict], bool] | None = None,
) -> dict:
    require_admin()
    reject_links(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("E_EXISTING_STATE")
    reject_links(backup)
    digest = sha256(backup)
    with installation_lock(target):
        installation = load_installation(target)
        platform = backend(installation, require_restore_capability=False)
        with verified_plaintext(
            backup, password, **plaintext_options(installation, platform)
        ) as (archive, manifest, _):
            if manifest["metadata"].get("installationId") != installation.state[
                "installationId"
            ] or not manifest["metadata"].get("portableDatabase"):
                raise ValueError("E_AUTHORITY_BACKUP_MISMATCH")
            archived_key = read_member(archive, "secrets/audit-integrity.key", 32)
            source_key = (target / "secrets/audit-integrity.key").read_bytes()
            if (
                not hmac.compare_digest(archived_key, source_key)
                or sha256(backup) != digest
            ):
                raise ValueError("E_AUTHORITY_BACKUP_MISMATCH")
            if review is not None:
                current = None
                if installation.state.get("authority") is None:
                    try:
                        current = json.loads(platform.command(COUNTS_SQL))
                    except (ValueError, OSError):
                        pass
                if not review(
                    {
                        "backupSha256": digest,
                        "sourceInstallationId": installation.state["installationId"],
                        "targetInstallationId": target_id,
                        "capturedAt": manifest["metadata"].get("capturedAt"),
                        "backupCounts": manifest["metadata"].get("verificationCounts"),
                        "currentCounts": current,
                    }
                ):
                    raise ValueError("E_CONFIRMATION")

            def stop_owned(installation):
                from update_worker import remove_schedule

                remove_schedule(installation)
                if installation.state.get("backend") == "windows-native":
                    from native_runtime import retire_services

                    retire_services(installation)
                else:
                    installation.compose("down", "--timeout", "30")

            receipt = retire(installation, target_id, digest, stop_owned)
        export_receipt(output, receipt)
        return {
            "sourceRetired": True,
            "targetInstallationId": target_id,
            "backupSha256": digest,
            "receiptExported": True,
        }


def validate_backup(manifest: dict, installation) -> dict:
    metadata = manifest["metadata"]
    if (
        not isinstance(metadata.get("configuration"), dict)
        or not isinstance(metadata["configuration"].get("release"), str)
        or not VERSION.fullmatch(metadata["configuration"]["release"])
        or "latest" in metadata["configuration"]["release"].lower()
        or type(metadata.get("postgresMajor")) is not int
        or metadata["postgresMajor"] != 17
        or type(metadata.get("schema")) is not int
        or metadata["schema"] != 49
        or not isinstance(metadata.get("portableDatabase"), dict)
        or not isinstance(metadata.get("verificationCounts"), dict)
        or set(metadata["verificationCounts"]) != {"users", "spaces", "audit"}
        or any(
            type(value) is not int or value < 0
            for value in metadata["verificationCounts"].values()
        )
        or metadata["verificationCounts"]["users"] < 1
        or metadata["verificationCounts"]["spaces"] != 1
    ):
        raise ValueError("E_RESTORE_COMPATIBILITY")
    try:
        source_id = str(uuid.UUID(metadata["installationId"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError("E_RESTORE_COMPATIBILITY") from None
    if source_id == installation.state["installationId"]:
        raise ValueError("E_RESTORE_TARGET_IDENTITY")
    return metadata


def disposition(platform, target_id: str, receipt: bytes, scratch: Path) -> None:
    request = scratch / "core-transfer.json"
    with private_output(request, scratch) as stream:
        stream.write(receipt)
        stream.flush()
        os.fsync(stream.fileno())
    platform.apply_disposition(request)
    if platform.command(
        "SELECT id::text FROM installation_identity WHERE singleton"
    ).strip().decode("ascii") != str(uuid.UUID(target_id)):
        raise ValueError("E_RESTORE_SECURITY")


def resume(
    installation, backup: Path, password: str, receipt_path: Path | None
) -> dict:
    """Caller holds the target lock; an inactive target can resume every phase."""
    request = installation.state.get("restoreRequest")
    if not isinstance(request, dict) or request.get("backupSha256") != sha256(backup):
        raise ValueError("E_RESTORE_REQUEST_CONFLICT")
    reconcile_managed(installation)
    platform = backend(installation)
    # A completed/activating transfer must never re-import over its live data.
    phase = installation.state.get("restore", {}).get("phase")
    if phase in {"activating", "active"}:
        platform.activate()
        installation.state["restore"]["phase"] = "active"
        installation.save()
        return summary(installation)
    with verified_plaintext(
        backup, password, **plaintext_options(installation, platform)
    ) as (archive, manifest, scratch):
        metadata = validate_backup(manifest, installation)
        source = metadata["installationId"]
        target_id = installation.state["installationId"]
        if receipt_path is None:
            return {
                "targetPrepared": True,
                "targetInstallationId": target_id,
                "sourceInstallationId": source,
                "backupSha256": request["backupSha256"],
                "awaitingSourceRetirement": True,
                "applicationActivated": False,
            }
        reject_links(receipt_path)
        if not receipt_path.is_file() or receipt_path.stat().st_size > 4096:
            raise ValueError("E_AUTHORITY_RECEIPT")
        key = read_member(archive, "secrets/audit-integrity.key", 32)
        receipt_raw = receipt_path.read_bytes()
        verify_receipt(receipt_raw, source, target_id, request["backupSha256"], key)
        if sha256(backup) != request["backupSha256"]:
            raise ValueError("E_RESTORE_REQUEST_CONFLICT")
        installation.state["restore"] = {
            "phase": "recovering"
            if installation.state.get("restoreSchemaPrepared")
            else "migrating",
            "sourceInstallationId": source,
            "receiptSha256": hashlib.sha256(receipt_raw).hexdigest(),
            "backupSha256": request["backupSha256"],
            "schema": metadata["schema"],
        }
        installation.save()
        # A failed import may have partial rows; never run Core over them. Only
        # start schema migration before the first import; subsequent retries use
        # the already generated trusted schema with all application services off.
        platform.stop_application()
        if installation.state.get("restoreSchemaPrepared") is not True:
            try:
                platform.start_schema()
            finally:
                platform.stop_application()
            if platform.command(SCHEMA_SQL).strip() != str(metadata["schema"]).encode(
                "ascii"
            ):
                raise ValueError("E_RESTORE_SCHEMA_MISMATCH")
            installation.state["restoreSchemaPrepared"] = True
            installation.save()
        else:
            # PostgreSQL alone may need to resume after a host restart.
            platform.ensure_database()
        installation.state["restore"]["phase"] = "importing"
        installation.save()
        rows = extract_rows(archive, manifest, scratch)
        restore_database(
            platform.command,
            lambda sql: platform.command(sql),
            platform.copy_in,
            metadata["portableDatabase"],
            rows,
        )
        if json.loads(platform.command(COUNTS_SQL)) != metadata["verificationCounts"]:
            raise ValueError("E_RESTORE_COUNTS")
        restore_keys_and_data(installation, archive, manifest)
        if "identity-provider.json" in manifest["files"]:
            from identity_settings import validate_identity

            identity = validate_identity(
                json.loads(
                    read_member(archive, "identity-provider.json", 4096),
                    object_pairs_hook=unique_object,
                )
            )
            replace_managed(
                installation,
                "identity-provider.json",
                json.dumps(identity, sort_keys=True).encode(),
            )
            installation.state["identityProvider"] = identity
            installation.save()
            if installation.state.get("backend") != "windows-native":
                lines = (installation.target / ".env").read_text().splitlines()
                lines = [
                    line
                    for line in lines
                    if not line.startswith(
                        (
                            "KYRION_CENTRAL_ENABLED=",
                            "KYRION_CENTRAL_ISSUER=",
                            "KYRION_CENTRAL_CLIENT_ID=",
                            "KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP=",
                        )
                    )
                ]
                lines.extend(
                    [
                        "KYRION_CENTRAL_ENABLED=true",
                        "KYRION_CENTRAL_ISSUER=" + identity["issuer"],
                        "KYRION_CENTRAL_CLIENT_ID=" + identity["clientId"],
                        "KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP="
                        + str(identity["allowLoopbackHttp"]).lower(),
                    ]
                )
                replace_managed(
                    installation, ".env", ("\n".join(lines) + "\n").encode()
                )
        disposition(platform, target_id, receipt_raw, scratch)
        space_id = str(
            uuid.UUID(
                platform.command("SELECT id::text FROM kyrion_space")
                .strip()
                .decode("ascii")
            )
        )
        recovery_key = installation.target / "recovery" / (space_id + ".host-key")
        reject_links(recovery_key)
        if recovery_key.is_file():
            installation.state["recoveryKey"] = {
                "spaceId": space_id,
                "sha256": sha256(recovery_key),
            }
            installation.state["recovery"] = "restored-host-key-needs-code-rotation"
        installation.verify_files()
        installation.state["restore"]["phase"] = "activating"
        installation.state["preparedForRestore"] = False
        installation.state["restore"]["reviewRequired"] = [
            "gateway-and-voice-reenrollment",
            "home-assistant-control-consent",
            "calendar-sync-schedule",
            "owner-recovery-code-rotation",
            "backup-and-update-policy",
        ]
        installation.save()
    platform.activate()
    installation.state["restore"]["phase"] = "active"
    installation.save()
    return summary(installation)


def summary(installation) -> dict:
    return {
        "targetInstallationId": installation.state["installationId"],
        "applicationActivated": installation.state["restore"]["phase"] == "active",
        "originalAccountsAndSpacePreserved": True,
        "oldSessionsRevoked": True,
        "schemaDowngradePerformed": False,
        "backupSha256": installation.state["restore"]["backupSha256"],
        "reviewRequired": installation.state["restore"].get("reviewRequired", []),
    }


def restore(
    target: Path,
    bundle: Path,
    public_key: Path,
    backup: Path,
    password: str,
    hostname: str,
    address: str,
    receipt: Path | None = None,
    worker: Path | None = None,
    ports: dict | None = None,
    *,
    expected_manifest: str | None = None,
    expected_backup: str | None = None,
) -> dict:
    require_admin()
    reject_links(backup)
    request = {"backupSha256": sha256(backup)}
    if expected_backup is not None and expected_backup != request["backupSha256"]:
        raise ValueError("E_REVIEW_CHANGED")
    if os.name == "nt":
        from native_bundle import authenticated_review
    else:
        from bundle import authenticated_review
    reviewed = authenticated_review(bundle, public_key)
    if expected_manifest is not None and reviewed.manifest_sha256 != expected_manifest:
        raise ValueError("E_REVIEW_CHANGED")
    if target.exists():
        with installation_lock(target):
            existing = load_installation(target, verify=False)
            if existing.state.get("restoreRequest") != request:
                raise ValueError("E_RESTORE_TARGET_NOT_EMPTY")
            if existing.configuration["manifestSha256"] != reviewed.manifest_sha256:
                raise ValueError("E_RESTORE_REQUEST_CONFLICT")
            if (
                existing.configuration["hostname"] != hostname
                or existing.configuration["address"] != address
            ):
                raise ValueError("E_RESTORE_REQUEST_CONFLICT")
            prepared = existing.state.get("restoreRuntimePrepared") is True
    else:
        prepared = False
    if not prepared:
        if os.name == "nt":
            from native_runtime import provision_native

            provision_native(
                target,
                bundle,
                public_key,
                hostname,
                address,
                reviewed.manifest_sha256,
                worker,
                ports=ports,
                restore_request=request,
            )
        else:
            from runtime import provision

            provision(
                target,
                bundle,
                public_key,
                hostname,
                address,
                reviewed.manifest_sha256,
                restore_request=request,
            )
    with installation_lock(target):
        # Only the explicit matching restore request may reconcile two-digest
        # file replacements after a crash; normal maintenance still verifies.
        installation = load_installation(target, verify=False)
        try:
            return resume(installation, backup, password, receipt)
        except (Exception, KeyboardInterrupt) as error:
            code = str(error).split(":", 1)[0]
            import re

            code = code if re.fullmatch(r"E_[A-Z_]{1,70}", code) else "E_INTERRUPTED"
            installation.state["lastError"] = code
            installation.state.setdefault("restore", {})["lastError"] = code
            try:
                installation.save()
            except OSError:
                pass
            raise
