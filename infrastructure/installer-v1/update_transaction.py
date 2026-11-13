"""Journaled single-host update/restore transactions over existing runtimes."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from authority import require_active
from bundle import sha256
from recovery import load_installation, verified_plaintext
from release_policy import verify
from runtime import installation_lock
from update_gate import FINAL
from update_state import path, phase, reconcile, select_configuration, transaction


def backend(installation):
    if installation.state.get("backend") == "windows-native":
        from update_native import Native

        return Native(installation)
    from update_compose import Compose

    return Compose(installation)


def _inputs(installation):
    """Resume the exact approval offline, not a new candidate from the internet."""
    from update_download import artifact_plan, validate_payload

    value = transaction(installation)
    saved = installation.state.get("updateDownload", {})
    if (
        saved.get("candidate") != value["candidate"]
        or saved.get("directory") != value["downloadDirectory"]
    ):
        raise ValueError("E_UPDATE_CHANGED")
    if not re.fullmatch(r"update-input/[a-f0-9]{24}", value["downloadDirectory"]):
        raise ValueError("E_UPDATE_CHANGED")
    root = installation.target / value["downloadDirectory"]
    for key, pattern in (
        ("indexProof", r"index-[a-f0-9]{12}\.json"),
        ("trustSnapshot", r"trust-[a-f0-9]{12}\.json"),
    ):
        if not isinstance(saved.get(key), str) or not re.fullmatch(pattern, saved[key]):
            raise ValueError("E_UPDATE_CHANGED")
    installation.verify_files()
    trust = json.loads((root / saved["trustSnapshot"]).read_bytes())
    index = verify(
        (root / saved["indexProof"]).read_bytes(),
        trust,
        "release-index",
        now=value["authorizedAt"],
    )
    if value["candidate"] not in index["releases"] or trust != value["trust"]:
        raise ValueError("E_UPDATE_CHANGED")
    raw = (root / "manifest.json").read_bytes()
    artifact_plan(raw, value["candidate"])
    return root, validate_payload(root, raw, value["candidate"])


def _backup(installation, platform, password: str, name="backup.gpg") -> dict:
    selected = path(installation, name)
    if not selected.exists():
        platform.capture(selected, password)
    with verified_plaintext(
        selected,
        password,
        executable=platform.gpg,
        environment=platform.environment,
        private_parent=installation.target,
        security_source=installation.target if os.name == "nt" else None,
    ) as (_archive, manifest, _scratch):
        metadata = manifest["metadata"]
        value = transaction(installation)
        expected_config = value["source"] if name == "backup.gpg" else value["target"]
        if (
            metadata.get("updateTransactionId") != value["id"]
            or metadata.get("installationId") != installation.state["installationId"]
            or metadata.get("configuration") != expected_config
            or metadata.get("schema")
            != (
                value["sourceSchema"]
                if name == "backup.gpg"
                else value["candidate"]["targetSchema"]
            )
        ):
            raise ValueError("E_UPDATE_BACKUP_MISMATCH")
        digest = sha256(selected)
        field = "backupSha256" if name == "backup.gpg" else "postActivationBackupSha256"
        if value.get(field) not in {None, digest}:
            raise ValueError("E_UPDATE_BACKUP_MISMATCH")
        value[field] = digest
        installation.save()
        platform.backup_manifest = manifest
        return copy.deepcopy(metadata)


def apply(target: Path, password: str, *, review, automatic=None) -> dict:
    from build_identity import read_build
    from operational_restore import require_admin
    from update_download import revalidate
    from update_worker import validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        if automatic is not None:
            from update_automatic import approved

            approved(installation, automatic, starting=True)
        if installation.state.get("backupServiceRecovery") is not None:
            raise ValueError("E_BACKUP_SERVICE_RECOVERY")
        if len(password) < 16 or any(ch in password for ch in "\r\n\x00"):
            raise ValueError("E_RECOVERY_PASSWORD")
        platform = backend(installation)
        schema = platform.schema()
        reviewed = revalidate(installation, read_build()["version"], schema)
        candidate = copy.deepcopy(installation.state["updateDownload"]["candidate"])
        original = platform.original()
        original["schema"] = schema
        original["identity"] = platform.identity()
        empty_identity_set = hashlib.sha256(b"").hexdigest()
        if any(
            original["identity"].get(name) == empty_identity_set
            for name in ("users", "spaces")
        ):
            # The Core audit transition needs an established account/Space.
            # Refuse an unfinished bootstrap before stopping any application.
            raise ValueError("E_UPDATE_SETUP_REQUIRED")
        knowledge_bytes = 0
        from host import reject_links

        for tree in (target / "data/knowledge", target / "recovery"):
            reject_links(tree)
            if tree.exists():
                for item in tree.rglob("*"):
                    reject_links(item)
                    if item.is_file():
                        knowledge_bytes += item.stat().st_size
        expansion = sum(row["bytes"] for row in reviewed.manifest.get("files", []))
        largest_archive = max(
            [row["bytes"] for row in reviewed.manifest.get("artifacts", [])] or [0]
        )
        needed = (
            original["databaseBytes"] * 6
            + knowledge_bytes * 3
            + expansion
            + largest_archive
            + 2 * 1024**3
        )
        if shutil.disk_usage(target).free < needed:
            raise ValueError("E_UPDATE_DISK")
        summary = {
            "sourceRelease": installation.configuration["release"],
            "targetRelease": candidate["version"],
            "sourceSchema": schema,
            "targetSchema": candidate["targetSchema"],
            "minimumFreeBytes": needed,
            "encryptedBackup": True,
            "applicationDowntime": True,
            "automaticSchemaDowngrade": False,
            "manifestSha256": reviewed.manifest_sha256,
            "scope": "single-host",
        }
        if not review(summary):
            raise ValueError("E_CONFIRMATION")
        authorized_at = int(time.time())
        reviewed = revalidate(
            installation,
            read_build()["version"],
            schema,
            verification_time=authorized_at,
        )
        identifier = str(uuid.uuid4())
        directory = target / installation.state["updateDownload"]["directory"]
        # Stage/verify all public code before application writers are stopped.
        configs = platform.stage(reviewed, directory, identifier, original)
        if automatic is not None:
            # Staging/download may have consumed the approved start window.
            approved(installation, automatic, starting=True)
        relative = "transaction/" + uuid.UUID(identifier).hex[:16]
        changes = {}
        aliases = {}
        for name, raw in configs.items():
            if name not in {"native-manifest.json", ".env", "compose.yml"}:
                raise ValueError("E_UPDATE_TRANSACTION")
            suffix = "compose" if name == "compose.yml" else "config"
            original_source = (target / name).read_bytes()
            source = getattr(platform, "source_configs", {}).get(name, original_source)
            if source != original_source:
                if name != "compose.yml":
                    raise ValueError("E_UPDATE_TRANSACTION")
                aliases[name] = hashlib.sha256(original_source).hexdigest()
                installation.write(relative + "/original-compose", original_source)
            changes[name] = {
                "source": hashlib.sha256(source).hexdigest(),
                "target": hashlib.sha256(raw).hexdigest(),
            }
            installation.write(relative + "/source-" + suffix, source)
            installation.write(relative + "/target-" + suffix, raw)
        installation.write(
            relative + "/maintenance.yml",
            'services:\n  core:\n    restart: "no"\n    environment:\n      KYRION_OPERATIONAL_MAINTENANCE: "true"\n',
        )
        source = copy.deepcopy(installation.configuration)
        previous = installation.state.get("updateTransaction")
        if previous is not None:
            previous = transaction(installation)
            if previous["phase"] not in FINAL:
                raise ValueError("E_UPDATE_IN_PROGRESS")
            # Preserve the final journal alongside its retained backup/runtime
            # before replacing the current transaction pointer.
            installation.write(
                previous["directory"] + "/completed.json",
                json.dumps(previous, sort_keys=True).encode(),
            )
        installation.state["updateTransaction"] = {
            "formatVersion": 1,
            "id": identifier,
            "phase": "preparing",
            "directory": relative,
            "authorizedAt": authorized_at,
            "actor": "AUTOMATIC" if automatic is not None else "HOST_ADMIN",
            "automaticApproval": copy.deepcopy(automatic),
            "source": source,
            "target": {
                **source,
                "release": candidate["version"],
                "manifestSha256": reviewed.manifest_sha256,
            },
            "sourceSchema": schema,
            "candidate": candidate,
            "original": {
                key: val for key, val in original.items() if key != "manifest"
            },
            "targetImages": getattr(platform, "target_images", None),
            "files": changes,
            "sourceAliases": aliases,
            "downloadDirectory": installation.state["updateDownload"]["directory"],
            "trust": installation.state["updatePolicy"]["trust"],
            "lastError": None,
        }
        installation.save()
        return _guarded(installation, platform, password)


def resume(target: Path, password: str, *, automatic=None) -> dict:
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target, verify=False)
        require_active(installation.state, update=True)
        if automatic is not None:
            from update_automatic import approved

            approved(installation, automatic, starting=False)
            value = transaction(installation)
            if (
                value.get("actor") != "AUTOMATIC"
                or value.get("automaticApproval") != automatic
            ):
                raise ValueError("E_UPDATE_AUTOMATIC_CONSENT")
            if value["phase"].startswith("recover") or value["phase"] == "reactivating":
                raise ValueError("E_UPDATE_AUTOMATIC_MANUAL")
        reconcile(installation)
        _inputs(installation)
        return _guarded(installation, backend(installation), password)


def _guarded(
    installation, platform, password, *, recovery=False, acknowledge_writes=False
):
    try:
        return (
            _recover(installation, platform, password, acknowledge_writes)
            if recovery
            else _continue(installation, platform, password)
        )
    except (Exception, KeyboardInterrupt) as error:
        code = str(error).split(":", 1)[0]
        value = transaction(installation)
        value["lastError"] = (
            code if re.fullmatch(r"E_[A-Z_]{1,80}", code) else "E_UPDATE_INTERRUPTED"
        )
        value["failedAt"] = int(time.time())
        installation.save()
        raise


def _continue(installation, platform, password):
    from update_database import snapshot

    value = transaction(installation)
    if value["phase"].startswith("recover") or value["phase"] == "reactivating":
        return _recover(installation, platform, password, False)
    if value["phase"] in FINAL:
        return result(installation)
    if value["phase"] == "preparing":
        if value.get("sourceAliases"):
            select_configuration(installation, "source")
        platform.quiesce()
        if hasattr(platform, "retain"):
            platform.retain()
        platform.admin("prepare", schema=value["sourceSchema"])
        phase(installation, "backing-up")
    if value["phase"] == "backing-up":
        platform.quiesce()
        _backup(installation, platform, password)
        phase(installation, "snapshotting")
    if value["phase"] == "snapshotting":
        platform.quiesce()
        metadata = _backup(installation, platform, password)
        platform.verify_snapshot_rows("kyrion", metadata)
        snapshot(platform, installation, metadata)
        phase(installation, "switching")
    if value["phase"] == "switching":
        select_configuration(installation, "target")
        platform.switch("target")
        phase(installation, "migrating")
    if value["phase"] in {"migrating", "checking"}:
        platform.maintenance()
        phase(installation, "checking")
        actual = platform.schema()
        if actual != value["candidate"]["targetSchema"]:
            raise ValueError("E_UPDATE_SCHEMA")
        if platform.identity() != value["original"]["identity"]:
            raise ValueError("E_UPDATE_IDENTITY_CHANGED")
        platform.stop_application()
        platform.admin("completed", schema=actual)
        value["observedSchema"] = actual
        phase(installation, "activating")
    if value["phase"] == "activating":
        platform.activate()
        value["lastError"] = None
        phase(installation, "complete")
    return result(installation)


def recover(target: Path, password: str, *, acknowledge_writes=False) -> dict:
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target, verify=False)
        require_active(installation.state, update=True)
        reconcile(installation)
        _inputs(installation)
        return _guarded(
            installation,
            backend(installation),
            password,
            recovery=True,
            acknowledge_writes=acknowledge_writes,
        )


def _recover(installation, platform, password, acknowledge_writes):
    from update_data import restore as restore_data
    from update_database import recover as restore_database

    value = transaction(installation)
    if value["phase"] == "recovered":
        return result(installation)
    if value["phase"] not in {
        "recovery-preparing",
        "recovering-runtime",
        "recovering-db",
        "recovery-checking",
        "reactivating",
    }:
        if value["phase"] in {"activating", "complete"} and not acknowledge_writes:
            raise ValueError("E_UPDATE_RECOVERY_WRITES_ACK_REQUIRED")
        after_activation = value["phase"] in {"activating", "complete"}
        value["databaseRecoveryRequired"] = value["phase"] in {
            "migrating",
            "checking",
            "activating",
            "complete",
        }
        value["postActivationWritesAcknowledged"] = after_activation
        phase(installation, "recovery-preparing")
    if value["phase"] == "recovery-preparing":
        platform.quiesce()
        if value["postActivationWritesAcknowledged"]:
            _backup(installation, platform, password, "post-activation.gpg")
        phase(installation, "recovering-runtime")
    if value["phase"] == "recovering-runtime":
        platform.stop_application()
        select_configuration(installation, "source")
        platform.switch("source")
        platform.ensure_database()
        phase(installation, "recovering-db")
    if value["phase"] == "recovering-db":
        if value["databaseRecoveryRequired"]:
            metadata = _backup(installation, platform, password)
            for name in ("secrets/credential.key", "secrets/audit-integrity.key"):
                if (
                    sha256(installation.target / name)
                    != platform.backup_manifest["files"][name]["sha256"]
                ):
                    raise ValueError("E_UPDATE_KEY_CHANGED")
            restore_database(platform, installation, metadata)
            with verified_plaintext(
                path(installation, "backup.gpg"),
                password,
                executable=platform.gpg,
                environment=platform.environment,
                private_parent=installation.target,
                security_source=installation.target if os.name == "nt" else None,
            ) as (archive, manifest, _scratch):
                restore_data(installation, archive, manifest)
        phase(installation, "recovery-checking")
    if value["phase"] == "recovery-checking":
        if platform.schema() != value["sourceSchema"]:
            raise ValueError("E_UPDATE_SCHEMA")
        platform.admin(
            "recovered" if value["databaseRecoveryRequired"] else "aborted",
            schema=value["sourceSchema"],
        )
        phase(installation, "reactivating")
    if value["phase"] == "reactivating":
        platform.activate()
        value["lastError"] = None
        phase(installation, "recovered")
    return result(installation)


def result(installation):
    value = transaction(installation)
    return {
        "transactionId": value["id"],
        "phase": value["phase"],
        "release": installation.configuration["release"],
        "complete": value["phase"] in FINAL,
        "recovered": value["phase"] == "recovered",
        "backupSha256": value.get("backupSha256"),
        "schemaDowngradeAttempted": False,
        "localSessionsRevoked": value["phase"] == "recovered"
        and value.get("databaseRecoveryRequired", False),
        "controlsRequireReview": value["phase"] == "recovered"
        and value.get("databaseRecoveryRequired", False),
        "postActivationWritesAcknowledged": value.get(
            "postActivationWritesAcknowledged", False
        ),
    }
