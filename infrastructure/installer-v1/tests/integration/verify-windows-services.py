"""Actual native services/virtual accounts/ACLs on disposable hosted Windows only.

This deliberately refuses an ordinary developer host. It registers only the
fresh UUID installation it creates, uses synthetic local credentials, and never
publishes a release or controls a household device. Host cold boot is separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import secrets
import shutil
import socket
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from native_bundle import authenticated_review
from native_runtime import (
    permissions,
    plan_for,
    provision_native,
    repair_native,
    stop_services,
)
from onboarding import CoreClient
from recovery import load_installation
from windows_service import ROLES, ServiceManager


def verify_native_update(target: Path, bundle: Path) -> None:
    """Real SCM/ACL update and recovery using a synthetic signed release label.

    Public binaries are unchanged; this tests the actual native lifecycle, not
    a new application migration. Migration faults have separate PG/Core tests.
    """
    from bundle import ReviewedBundle, sha256
    from native_bundle import validate
    from update_transaction import apply, recover, resume

    installation = load_installation(target)
    worker = installation.state["updatePolicy"]["workerFile"]
    source_identity = installation.state["installationId"]
    original_manifest = installation.configuration["manifestSha256"]
    stage = target / "ci-update-public"
    stage.mkdir()
    document = json.loads((bundle / "manifest.json").read_bytes())
    document["release"] = "1.2.0"
    (stage / "manifest.json").write_text(json.dumps(document), encoding="utf-8")
    shutil.copyfile(
        bundle / document["artifact"]["name"], stage / document["artifact"]["name"]
    )
    validate(stage)
    reviewed = ReviewedBundle(document, sha256(stage / "manifest.json"))
    fixtures = runpy.run_path(
        str(Path(__file__).with_name("verify-update-transaction.py"))
    )
    fixtures["signed_inputs"](
        installation, stage, reviewed, target_schema=document["compatibility"]["schema"]
    )
    installation.state["updatePolicy"]["workerFile"] = worker
    installation.save()
    password = "Synthetic-native-update-recovery-123456"
    # Only source-driver build identity is injected to authorize the synthetic
    # test index. Installed service hosts, SQL, TLS, GPG, ACLs and SCM are real.
    with patch("build_identity.read_build", return_value={"version": "1.0.0"}):
        complete = apply(target, password, review=lambda _: True)
        if not complete["complete"] or complete["phase"] != "complete":
            raise ValueError("E_TEST_NATIVE_UPDATE")
        resume(target, password)
        recovered = recover(target, password, acknowledge_writes=True)
    final = load_installation(target)
    if (
        not recovered["recovered"]
        or final.state["installationId"] != source_identity
        or final.configuration["manifestSha256"] != original_manifest
    ):
        raise ValueError("E_TEST_NATIVE_UPDATE_RECOVERY")
    permissions(target, "verify-payload")
    with ServiceManager() as scm:
        for role in ROLES:
            plan = plan_for(final, role)
            with scm.opened(plan["name"]) as handle:
                status = scm.assert_owned(handle, plan)
                if status["state"] != 4 or status["start"] != 2:
                    raise ValueError("E_TEST_NATIVE_UPDATE_SERVICE_STATE")


def free_ports() -> dict:
    values = {}
    for role in ROLES:
        while True:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            if port not in values.values():
                values[role] = port
                break
    return values


def cleanup_owned_target(target: Path, parent: Path) -> None:
    if target.resolve().parent != parent.resolve() or not target.name.startswith(
        "KyrionCI-"
    ):
        raise ValueError("E_TEST_CLEANUP_SCOPE")
    uuid.UUID(target.name.removeprefix("KyrionCI-"))
    journal = target / "install-state.json"
    if journal.is_file() and all(
        (target / name).is_file()
        for name in ("installer.exe", "native-runtime.json", "native-manifest.json")
    ):
        installation = load_installation(target, verify=False)
        from update_worker import remove_schedule

        remove_schedule(installation)
        # Explicitly clean the owned intermediate initializer as well after
        # an interrupted/failed initialization, never an arbitrary service.
        with ServiceManager(writable=True) as scm:
            for role in reversed(ROLES):
                plan = plan_for(installation, role)
                with scm.opened(plan["name"], mutate=True) as handle:
                    if handle:
                        try:
                            scm.assert_owned(handle, plan)
                        except ValueError:
                            if role != "postgres":
                                raise
                            plan = plan_for(installation, "postgres-init")
                            scm.assert_owned(handle, plan)
                        scm.remove(handle, plan)
                scm.wait_removed(plan["name"])
    if target.exists():
        if target.parent != parent or not target.name.startswith("KyrionCI-"):
            raise ValueError("E_TEST_CLEANUP_SCOPE")
        for _ in range(30):
            try:
                shutil.rmtree(target)
                break
            except PermissionError:
                time.sleep(1)
        else:
            raise ValueError("E_TEST_CLEANUP_INCOMPLETE")


def verify_update_task(target: Path, worker: Path) -> None:
    """Actual SYSTEM execution of a dev worker; intentionally no release fetch."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from update_schedule import operate
    from update_worker import remove_schedule
    from windows_tasks import operate as task_operation
    from windows_tasks import update_check_plan

    installation = load_installation(target)
    public_key = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    raw = worker.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    name = "maintenance-" + digest[:32] + ".exe"
    installation.write(name, raw)
    installation.state["updatePolicy"] = {
        "formatVersion": 1,
        "revision": str(uuid.uuid4()),
        "enabled": True,
        "feed": "https://updates.invalid.example.test/index.json",
        "trust": {
            "formatVersion": 1,
            "epoch": 1,
            "keys": [
                {
                    "id": "fixture",
                    "pem": public_key,
                    "notBefore": int(time.time()) - 60,
                    "notAfter": int(time.time()) + 3600,
                    "usages": ["release-index", "trust-rotation"],
                }
            ],
        },
        "workerFile": name,
    }
    installation.save()
    try:
        actual = operate(installation, "register")
        if actual["state"] != "registered" or actual["coldBootVerified"]:
            raise ValueError("E_TEST_UPDATE_SCHEDULE")
        installation.state["updateSchedule"] = actual
        installation.save()
        operate(installation, "register")
        plan = update_check_plan(
            installation.state["installationId"], str(target), name
        )
        task_operation(plan, "start")
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            installation = load_installation(target)
            attempt = installation.state.get("updateAttempt")
            if attempt is not None:
                if attempt.get(
                    "error"
                ) != "E_INSTALLER_UNRELEASED" or installation.state.get("updateCheck"):
                    raise ValueError("E_TEST_UNRELEASED_WORKER_FETCH")
                break
            time.sleep(1)
        else:
            raise ValueError("E_TEST_UPDATE_WORKER_TIMEOUT")
    finally:
        remove_schedule(load_installation(target))


def main(bundle: Path, key: Path, worker: Path) -> dict:
    if (
        os.name != "nt"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
        or not os.environ.get("GITHUB_RUN_ID", "").isdigit()
    ):
        raise ValueError("E_DISPOSABLE_WINDOWS_RUNNER_REQUIRED")
    parent = Path(os.environ["ProgramData"]).resolve()
    target = parent / ("KyrionCI-" + uuid.uuid4().hex)
    if target.exists():
        raise ValueError("E_TEST_TARGET_EXISTS")
    checked = authenticated_review(bundle, key)
    ports = free_ports()
    password = secrets.token_urlsafe(24)
    restored_target = None
    try:
        state = provision_native(
            target,
            bundle,
            key,
            "fixture.test",
            "127.0.0.1",
            checked.manifest_sha256,
            worker,
            ports,
        )
        if state["stage"] != "services-healthy":
            raise ValueError("E_TEST_SERVICES_NOT_READY")
        installation = load_installation(target)
        client = CoreClient(installation)
        try:
            owner = client.login_or_setup(
                "fixture-owner", password, "Native SCM fixture", "HOME"
            )
            if "OWNER" not in owner.get("roles", []):
                raise ValueError("E_TEST_OWNER")
            client.request("GET", "/v1/space")
            client.request("GET", "/v1/devices")
        finally:
            client.close()
        permissions(target, "verify-payload")
        # The actual service identities performed their own negative secret and
        # write-access checks before reporting RUNNING.
        for role in ("core", "web", "caddy"):
            report = json.loads(
                (target / "data" / role / "service-status.json").read_text()
            )
            if not all(
                report.get(field) is True
                for field in (
                    "verified",
                    "secretBoundaryChecked",
                    "runtimeReadOnlyChecked",
                )
            ):
                raise ValueError("E_TEST_RUNTIME_ACCESS")
        with ServiceManager() as scm:
            for role in ROLES:
                plan = plan_for(installation, role)
                with scm.opened(plan["name"]) as handle:
                    if not handle:
                        raise ValueError("E_TEST_SERVICE_MISSING")
                    config = scm.assert_owned(handle, plan)
                    if config["start"] != 2 or config["state"] != 4:
                        raise ValueError("E_TEST_AUTOSTART")
        # Repeat the real provisioner: secrets and identity must stay stable.
        keys = {
            name: (target / "secrets" / name).read_bytes()
            for name in ("credential.key", "audit-integrity.key", "postgres-password")
        }
        repeated = provision_native(
            target,
            bundle,
            key,
            "fixture.test",
            "127.0.0.1",
            checked.manifest_sha256,
            worker,
            ports,
        )
        if repeated["installationId"] != state["installationId"]:
            raise ValueError("E_TEST_DUPLICATE_IDENTITY")
        for name, value in keys.items():
            if (target / "secrets" / name).read_bytes() != value:
                raise ValueError("E_TEST_KEY_ROTATION")
        stop_services(load_installation(target))
        repair_native(target)
        client = CoreClient(load_installation(target))
        try:
            owner = client.login_or_setup("fixture-owner", password)
            if "OWNER" not in owner.get("roles", []):
                raise ValueError("E_TEST_RESTART_LOGIN")
            if (
                client.request("GET", "/v1/auth/setup/status").get("setupRequired")
                is not False
            ):
                raise ValueError("E_TEST_SETUP_REOPENED")
        finally:
            client.close()
        verify_update_task(target, worker)
        verify_native_update(target, bundle)
        # Actual privileged backup capture is restricted to this fresh synthetic
        # installation. It is not a full application restore/identity acceptance.
        from native_backup import backup
        from recovery import crypto, inspect_archive

        encrypted = target / "service-backup.gpg"
        clear = target / "service-backup-check.tar"
        recovery_password = "Synthetic-service-backup-password-123456"
        captured = backup(target, encrypted, recovery_password)
        crypto(
            encrypted,
            clear,
            recovery_password,
            True,
            executable=target / "payload/runtime/installer/gnupg/bin/gpg.exe",
        )
        archive = inspect_archive(clear)
        from native_runtime import installed_schema

        if (
            captured.get("restoreVerified") is not False
            or archive["metadata"]["verificationCounts"]["users"] != 1
            or archive["metadata"]["verificationCounts"]["spaces"] != 1
            or "secrets/credential.key" not in archive["files"]
            or any(name.startswith("payload/") for name in archive["files"])
            or installed_schema(load_installation(target))
            != str(archive["metadata"]["schema"])
        ):
            raise ValueError("E_TEST_NATIVE_BACKUP")
        clear.unlink()
        if load_installation(target).state.get("backupServiceRecovery") is not None:
            raise ValueError("E_TEST_NATIVE_BACKUP_SERVICE_RECOVERY")
        from operational_restore import restore, retire_source

        restored_target = parent / ("KyrionCI-" + str(uuid.uuid4()))
        restored_ports = free_ports()
        prepared = restore(
            restored_target,
            bundle,
            key,
            encrypted,
            recovery_password,
            "fixture.test",
            "127.0.0.1",
            worker=worker,
            ports=restored_ports,
        )
        if prepared.get("applicationActivated") or not prepared.get(
            "awaitingSourceRetirement"
        ):
            raise ValueError("E_TEST_RESTORE_PREMATURE_ACTIVATION")
        receipt_path = target / "transfer-receipt.json"
        retire_source(
            target,
            encrypted,
            recovery_password,
            prepared["targetInstallationId"],
            receipt_path,
        )
        restored = restore(
            restored_target,
            bundle,
            key,
            encrypted,
            recovery_password,
            "fixture.test",
            "127.0.0.1",
            receipt_path,
            worker,
            restored_ports,
        )
        if not restored["applicationActivated"]:
            raise ValueError("E_TEST_RESTORE_ACTIVATION")
        restored_client = CoreClient(load_installation(restored_target))
        try:
            owner = restored_client.login_or_setup("fixture-owner", password)
            if "OWNER" not in owner.get("roles", []):
                raise ValueError("E_TEST_RESTORE_OFFLINE_LOGIN")
        finally:
            restored_client.close()
        try:
            repair_native(target)
        except ValueError as error:
            if str(error) != "E_AUTHORITY_INACTIVE":
                raise
        else:
            raise ValueError("E_TEST_RETIRED_SOURCE_REPAIRED")
        with ServiceManager() as scm:
            old = load_installation(target)
            for role in ROLES:
                plan = plan_for(old, role)
                with scm.opened(plan["name"]) as handle:
                    status = scm.assert_owned(handle, plan)
                    if status["start"] != 4 or status["state"] != 1:
                        raise ValueError("E_TEST_RETIRED_SOURCE_NOT_DISABLED")
        return {
            "actualWindowsServices": True,
            "dedicatedVirtualAccounts": True,
            "actualNegativeSecretAccessChecks": True,
            "realApplicationSetup": True,
            "repeatedProvisioning": True,
            "keysPreserved": True,
            "serviceRestartLogin": True,
            "autostartConfigurationVerified": True,
            "payloadOwnershipAndReadOnlyPolicyVerified": True,
            "nativeConsistentEncryptedCaptureVerified": True,
            "nativeFullRestoreVerified": True,
            "retiredSourceStoppedDisabledAndRepairDenied": True,
            "nativeInstalledSchemaQueryVerified": True,
            "actualSystemUpdateTaskExecution": True,
            "nativeSingleHostUpdateAndSnapshotRecovery": True,
            "syntheticReleaseLabelUnchangedPublicBinaries": True,
            "updateWorkerRefusesUnreleasedBuildBeforeNetwork": True,
            "coldBootVerified": False,
            "networkIsolated": False,
            "runtimeManifestSha256": checked.manifest_sha256,
        }
    finally:
        cleanup_owned_target(target, parent)
        if restored_target is not None:
            cleanup_owned_target(restored_target, parent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "key", "worker", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = main(args.bundle.resolve(), args.key.resolve(), args.worker.resolve())
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
