"""Actual native services/virtual accounts/ACLs on disposable hosted Windows only.

This deliberately refuses an ordinary developer host. It registers only the
fresh UUID installation it creates, uses synthetic local credentials, and never
publishes a release or controls a household device. Host cold boot is separate.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import sys
import time
import uuid
from pathlib import Path

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
        encrypted.unlink()
        if load_installation(target).state.get("backupServiceRecovery") is not None:
            raise ValueError("E_TEST_NATIVE_BACKUP_SERVICE_RECOVERY")
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
            "nativeFullRestoreVerified": False,
            "nativeInstalledSchemaQueryVerified": True,
            "coldBootVerified": False,
            "networkIsolated": False,
            "runtimeManifestSha256": checked.manifest_sha256,
        }
    finally:
        journal = target / "install-state.json"
        if journal.is_file() and all(
            (target / name).is_file()
            for name in ("installer.exe", "native-runtime.json", "native-manifest.json")
        ):
            installation = load_installation(target, verify=False)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "key", "worker", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = main(args.bundle.resolve(), args.key.resolve(), args.worker.resolve())
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
