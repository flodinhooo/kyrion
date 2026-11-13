"""Explicit local maintenance on the existing installation authority."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from bundle import sha256
from host import reject_links, runtime_checks
from recovery import backup, load_installation, verify_database
from runtime import ROOT, installation_lock


def check_updates(
    args,
    *,
    trusted_document=None,
    policy_revision=None,
    capture_proof=None,
    require_enabled=True,
) -> dict:
    from release_policy import (
        compatible_release,
        fetch_document,
        parse,
        verify,
        version,
    )

    try:
        version(args.installer_version)
    except ValueError:
        raise ValueError("E_INSTALLER_UNRELEASED") from None

    if not args.feed or (args.trust_store is None and trusted_document is None):
        raise ValueError("E_UPDATE_CONFIG")
    if args.trust_store is not None:
        reject_links(args.trust_store)
    with installation_lock(args.target):
        installation = load_installation(args.target)
        from authority import require_active

        require_active(installation.state)
        if policy_revision is not None:
            policy = installation.state.get("updatePolicy", {})
            if (
                policy.get("revision") != policy_revision
                or (require_enabled and policy.get("enabled") is not True)
                or policy.get("feed") != args.feed
                or policy.get("trust") != trusted_document
            ):
                raise ValueError("E_UPDATE_POLICY_CHANGED")
        if installation.state.get("backend") == "windows-native":
            from native_runtime import installed_schema

            schema_text = installed_schema(installation)
        else:
            runtime_checks(
                installation.configuration["address"],
                installation.configuration["hostname"],
                fresh=False,
            )
            schema_text = installation.compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "kyrion",
                "-d",
                "kyrion",
                "-Atc",
                "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'",
            ).strip()
        if not schema_text.isdigit() or (
            args.installed_schema is not None
            and int(schema_text) != args.installed_schema
        ):
            raise ValueError("E_UPDATE_SCHEMA")
        trust = (
            trusted_document
            if trusted_document is not None
            else parse(args.trust_store.read_bytes())
        )
        envelope = fetch_document(args.feed)
        index = verify(envelope, trust, "release-index")
        previous = installation.state.get("updateCheck", {})
        index_digest = hashlib.sha256(
            json.dumps(index, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if trust["epoch"] < previous.get("trustEpoch", 0):
            raise ValueError("E_UPDATE_TRUST_ROLLBACK")
        if index.get("sequence") == previous.get("sequence") and previous.get(
            "indexSha256"
        ) not in {None, index_digest}:
            raise ValueError("E_UPDATE_INDEX_EQUIVOCATION")
        selected = compatible_release(
            index,
            args.installer_version,
            installation.configuration["release"],
            installation.configuration["architecture"],
            int(schema_text),
            args.installed_api,
            previous.get("sequence", 0),
        )
        import time

        result = {
            "checkedAt": int(time.time()),
            "sequence": index["sequence"],
            "available": selected is not None,
            "candidate": selected,
            "installedAutomatically": False,
            "indexSha256": index_digest,
            "trustEpoch": trust["epoch"],
            "feed": args.feed,
        }
        installation.state["updateCheck"] = result
        installation.save()
        if capture_proof is not None:
            capture_proof(envelope)
        return result


def diagnostic(target: Path, output: Path) -> None:
    installation = load_installation(target, verify=False)
    reject_links(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("E_EXISTING_STATE")
    state = installation.state
    error = state.get("lastError")
    report = {
        "formatVersion": 1,
        "reportId": str(uuid.uuid4()),
        "release": installation.configuration["release"],
        "architecture": installation.configuration["architecture"],
        "stage": state.get("stage")
        if state.get("stage")
        in {"reviewed", "configured", "starting", "services-healthy", "uninstalled"}
        else "unknown",
        "lastError": error
        if isinstance(error, str) and re.fullmatch(r"E_[A-Z_]{1,80}", error)
        else None,
        "ownerSetup": state.get("ownerSetup") == "authenticated",
        "backupConfigured": state.get("backup") == "encrypted-consistent-capture",
        "updatesConfigured": (
            state.get("updatePolicy", {}).get("enabled") is True
            and state.get("updateSchedule", {}).get("state") == "registered"
        ),
        "managedFilesIntact": False,
    }
    try:
        installation.verify_files()
        report["managedFilesIntact"] = True
    except ValueError:
        pass
    # No raw state, child output, environment, usernames, host paths, endpoint
    # credentials, file contents or service logs enter this allowlisted report.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    os.chmod(output, 0o600)


def repair(target: Path) -> dict:
    with installation_lock(target):
        installation = load_installation(target, verify=False)
        from authority import require_active

        require_active(installation.state)
        config = installation.configuration
        runtime_checks(config["address"], config["hostname"], fresh=False)
        candidates = {
            "compose.yml": (ROOT / "templates/compose.yml")
            .read_text(encoding="utf-8")
            .encode("utf-8"),
            "data/Caddyfile": (ROOT / "templates/Caddyfile")
            .read_text(encoding="utf-8")
            .replace("__KYRION_HOSTNAME__", config["hostname"])
            .encode(),
            ".env": (
                "\n".join(
                    [
                        "KYRION_RELEASE=" + config["release"],
                        "KYRION_HOSTNAME=" + config["hostname"],
                        "KYRION_BIND_ADDRESS=" + config["address"],
                        "KYRION_DATA_DIR=" + str(target / "data"),
                        "KYRION_SECRETS_DIR=" + str(target / "secrets"),
                        "",
                    ]
                )
            ).encode(),
        }
        damaged = []
        # Inspect every file before any repair write. Missing/changed keys and
        # unknown configuration are never replaced by generated material.
        for name, expected in installation.state["files"].items():
            path = target / name
            reject_links(path)
            if path.is_file() and sha256(path) == expected:
                continue
            value = candidates.get(name)
            if value is None or hashlib.sha256(value).hexdigest() != expected:
                raise ValueError("E_REPAIR_ORIGINAL_REQUIRED")
            damaged.append((name, value))
        for name, value in damaged:
            path = target / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if path.exists():
                path.rename(
                    path.with_name(path.name + ".repair-original-" + uuid.uuid4().hex)
                )
            with os.fdopen(
                os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
        installation.verify_files()
        installation.start()
        return {
            "repairedFiles": [name for name, _ in damaged],
            "stage": installation.state["stage"],
        }


def uninstall(target: Path, purge: bool = False) -> dict:
    with installation_lock(target):
        installation = load_installation(target)
        from update_worker import remove_schedule

        remove_schedule(installation)
        config = installation.configuration
        runtime_checks(config["address"], config["hostname"], fresh=False)
        # Compose project identity is installation-scoped. No image removal,
        # volume pruning, shared Docker uninstall or foreign Ollama deletion.
        installation.compose("down", "--timeout", "30")
        installation.state["stage"] = "uninstalled"
        installation.save()
        if purge:
            reject_links(target)
            for child in target.rglob("*"):
                reject_links(child)
            shutil.rmtree(target)
        return {
            "softwareRemoved": True,
            "dataRemoved": purge,
            "sharedResourcesRemoved": False,
        }


def run(args, messages: dict[str, str]) -> int:
    if input(messages["maintenanceReview"] + " [MAINTAIN]: ").strip() != "MAINTAIN":
        print(messages["cancelled"])
        return 0
    if getattr(args, "updates", None):
        from update_worker import configure, remove_schedule, rotate_policy

        if args.updates == "download":
            from update_download import download

            def review_download(summary):
                print(messages["updatesDownloadReview"])
                print(json.dumps(summary))
                return input("[DOWNLOAD-UPDATE]: ").strip() == "DOWNLOAD-UPDATE"

            import time

            last_progress = (None, 0.0)

            def show_progress(name, received, total):
                nonlocal last_progress
                now = time.monotonic()
                if (
                    last_progress[0] != name
                    or now - last_progress[1] >= 1
                    or received == total
                ):
                    print(
                        messages["updatesDownloadProgress"]
                        + " "
                        + json.dumps(
                            {
                                "artifact": name,
                                "receivedBytes": received,
                                "artifactBytes": total,
                            }
                        ),
                        flush=True,
                    )
                    last_progress = (name, now)

            print(
                json.dumps(
                    download(
                        args.target, review=review_download, progress=show_progress
                    )
                )
            )
        elif args.updates == "configure":
            if not args.feed or args.trust_store is None:
                raise ValueError("E_UPDATE_CONFIG")
            print(messages["updatesScheduleReview"])
            import sys

            worker_digest = sha256(Path(sys.executable))
            print(
                json.dumps(
                    {
                        "feed": args.feed,
                        "trustStore": str(args.trust_store),
                        "workerSha256": worker_digest,
                    }
                )
            )
            if input("[ENABLE-CHECKS]: ").strip() != "ENABLE-CHECKS":
                raise ValueError("E_CONFIRMATION")
            print(
                json.dumps(
                    configure(args.target, args.feed, args.trust_store, worker_digest)
                )
            )
        elif args.updates == "rotate-trust":
            if args.trust_rotation is None:
                raise ValueError("E_UPDATE_CONFIG")
            digest = sha256(args.trust_rotation)
            print(messages["updatesTrustReview"])
            print(json.dumps({"rotationSha256": digest}))
            if input("[ROTATE-TRUST]: ").strip() != "ROTATE-TRUST":
                raise ValueError("E_CONFIRMATION")
            print(json.dumps(rotate_policy(args.target, args.trust_rotation, digest)))
        else:
            with installation_lock(args.target):
                installation = load_installation(args.target)
                if args.updates == "disable":
                    from operational_restore import require_admin

                    require_admin()
                    remove_schedule(installation)
                print(messages["updatesStatus"])
                print(
                    json.dumps(
                        {
                            "schedule": installation.state.get("updateSchedule"),
                            "lastAttempt": installation.state.get("updateAttempt"),
                            "lastSuccessfulCheck": installation.state.get(
                                "updateCheck"
                            ),
                            "automaticInstallation": False,
                        }
                    )
                )
        return 0
    if getattr(args, "retire_for_restore", None):
        from operational_restore import retire_source

        if not args.restore_target_id or args.transfer_receipt is None:
            raise ValueError("E_AUTHORITY_RECEIPT_ARGUMENTS")
        print(
            json.dumps(
                {
                    "source": str(args.target),
                    "targetInstallationId": args.restore_target_id,
                    "backupSha256": sha256(args.retire_for_restore),
                }
            )
        )

        def review_retirement(summary):
            print(json.dumps(summary))
            return (
                input(messages["restoreRetireReview"] + " [RETIRE-SOURCE]: ").strip()
                == "RETIRE-SOURCE"
            )

        password = getpass.getpass(messages["backupPassword"] + ": ")
        print(
            json.dumps(
                retire_source(
                    args.target,
                    args.retire_for_restore,
                    password,
                    args.restore_target_id,
                    args.transfer_receipt,
                    review=review_retirement,
                )
            )
        )
        return 0
    if getattr(args, "restore", None):
        from operational_restore import restore

        if args.public_key is None:
            raise ValueError("E_SIGNATURE_TRUST_REQUIRED")
        if os.name == "nt":
            from native_bundle import authenticated_review
        else:
            from bundle import authenticated_review
        reviewed = authenticated_review(args.bundle, args.public_key)
        backup_digest = sha256(args.restore)
        existing = (
            load_installation(args.target, verify=False)
            if args.target.exists()
            else None
        )
        hostname = args.restore_hostname or (
            existing.configuration["hostname"]
            if existing
            else input(messages["hostname"] + ": ").strip()
        )
        address = args.restore_address or (
            existing.configuration["address"]
            if existing
            else input(messages["address"] + ": ").strip()
        )
        print(
            json.dumps(
                {
                    "target": str(args.target),
                    "release": reviewed.manifest["release"],
                    "manifestSha256": reviewed.manifest_sha256,
                    "backupBytes": args.restore.stat().st_size,
                    "backupSha256": backup_digest,
                    "runtimeArtifacts": reviewed.manifest.get(
                        "artifacts", [reviewed.manifest.get("artifact")]
                    ),
                    "components": reviewed.manifest.get("components"),
                    "hostname": hostname,
                    "address": address,
                }
            )
        )
        if (
            input(messages["restoreReview"] + " [RESTORE-TO-NEW-TARGET]: ").strip()
            != "RESTORE-TO-NEW-TARGET"
        ):
            raise ValueError("E_CONFIRMATION")
        password = getpass.getpass(messages["backupPassword"] + ": ")
        result = restore(
            args.target,
            args.bundle,
            args.public_key,
            args.restore,
            password,
            hostname,
            address,
            args.transfer_receipt,
            expected_manifest=reviewed.manifest_sha256,
            expected_backup=backup_digest,
        )
        print(json.dumps(result))
        if result.get("awaitingSourceRetirement"):
            print(messages["restoreAwaitingRetirement"])
        else:
            print(messages["restoreReviewRequired"])
        return 0
    if args.diagnostics:
        diagnostic(args.target, args.diagnostics)
        print(messages["diagnosticSaved"])
        return 0
    if getattr(args, "home_assistant", None):
        from linked_onboarding import linked_setup
        from onboarding import CoreClient, guided_home_assistant

        with installation_lock(args.target):
            installation = load_installation(args.target)
            if installation.state.get("backend") == "windows-native":
                from native_runtime import permissions

                permissions(args.target, "verify")
            elif os.name != "posix" or os.geteuid() != 0:
                raise ValueError("E_PLATFORM")
            client = CoreClient(installation)
            try:
                linked_setup(client, messages)
                if args.home_assistant == "configure":
                    guided_home_assistant(client, messages)
                elif args.home_assistant == "disconnect":
                    if (
                        input(
                            messages["haDisconnectReview"] + " [DISCONNECT/CANCEL]: "
                        ).strip()
                        != "DISCONNECT"
                    ):
                        raise ValueError("E_CONFIRMATION")
                    result = client.request("DELETE", "/v1/integrations/home-assistant")
                    status = client.request("GET", "/v1/integrations/home-assistant")
                    if status.get("configured") is not False:
                        raise ValueError("E_HA_DISCONNECT")
                    installation.state["homeAssistant"] = "disconnected"
                    installation.save()
                    print(
                        json.dumps(
                            {
                                "disconnected": result.get("disconnected") is True,
                                "configured": False,
                            }
                        )
                    )
                else:
                    print(
                        json.dumps(
                            client.request("GET", "/v1/integrations/home-assistant"),
                            ensure_ascii=True,
                        )
                    )
            finally:
                client.close()
        return 0
    if getattr(args, "owner_recovery", None):
        from onboarding import provision_recovery

        if (
            input(
                messages["recoveryMaintenanceReview"] + " [RECOVERY/CANCEL]: "
            ).strip()
            != "RECOVERY"
        ):
            raise ValueError("E_CONFIRMATION")
        with installation_lock(args.target):
            installation = load_installation(args.target)
            selected = installation.state.get("selectedSpace", {})
            space = getattr(args, "recovery_space", None) or selected.get("id")
            if not isinstance(space, str):
                raise TypeError("E_RECOVERY_SPACE_REQUIRED")
            provision_recovery(
                installation, str(uuid.UUID(space)), messages, args.owner_recovery
            )
        return 0
    if getattr(args, "continue_setup", False):
        from onboarding import guided_setup

        with installation_lock(args.target):
            installation = load_installation(args.target)
            if installation.state.get("backend") == "windows-native":
                from native_runtime import permissions

                permissions(args.target, "verify")
            elif os.name != "posix" or os.geteuid() != 0:
                raise ValueError("E_PLATFORM")
            guided_setup(installation, messages)
            print(
                json.dumps(
                    {
                        "ownerSetup": installation.state.get("ownerSetup"),
                        "centralIdentity": installation.state.get(
                            "centralIdentity", "not-verified"
                        ),
                        "selectedSpace": installation.state.get("selectedSpace"),
                    }
                )
            )
        return 0
    if getattr(args, "extend_bootstrap", False):
        from bootstrap_maintenance import extend_bootstrap

        if (
            input(messages["bootstrapExtendReview"] + " [EXTEND/CANCEL]: ").strip()
            != "EXTEND"
        ):
            raise ValueError("E_CONFIRMATION")
        with installation_lock(args.target):
            installation = load_installation(args.target)
            print(json.dumps(extend_bootstrap(installation)))
        return 0
    if args.refresh_model_catalog:
        from model_cache import refresh_catalog
        from release_policy import parse

        if not args.feed or args.trust_store is None:
            raise ValueError("E_MODEL_TRUST_REQUIRED")
        reject_links(args.trust_store)
        if args.trust_store.stat().st_size > 256 * 1024:
            raise ValueError("E_TRUST_STORE")
        with installation_lock(args.target):
            installation = load_installation(args.target)
            if installation.state.get("backend") == "windows-native":
                from native_runtime import permissions

                permissions(args.target, "verify")
            elif os.name != "posix" or os.geteuid() != 0:
                raise ValueError("E_PLATFORM")
            result = refresh_catalog(
                installation, args.feed, parse(args.trust_store.read_bytes())
            )
        print(json.dumps(result))
        return 0
    if os.name == "nt" and (args.repair or args.uninstall):
        from native_runtime import repair_native, uninstall_native

        if args.repair:
            print(json.dumps(repair_native(args.target)))
        else:
            purge = (
                args.delete_data
                and input(messages["deleteDataReview"] + " [DELETE-DATA]: ").strip()
                == "DELETE-DATA"
            )
            if args.delete_data and not purge:
                raise ValueError("E_CONFIRMATION")
            print(json.dumps(uninstall_native(args.target, purge)))
        return 0
    if os.name == "nt" and args.backup:
        from native_backup import backup as native_backup

        password = getpass.getpass(messages["backupPassword"] + ": ")
        if password != getpass.getpass(messages["repeatPassword"] + ": "):
            raise ValueError("E_PASSWORD_MISMATCH")
        print(json.dumps(native_backup(args.target, args.backup, password)))
        return 0
    if os.name == "nt" and args.check_updates:
        print(json.dumps(check_updates(args)))
        return 0
    if os.name != "posix" or os.geteuid() != 0:
        raise ValueError("E_PLATFORM: supported Linux root maintenance required")
    if args.check_updates:
        print(json.dumps(check_updates(args)))
    elif args.backup:
        password = getpass.getpass(messages["backupPassword"] + ": ")
        if password != getpass.getpass(messages["repeatPassword"] + ": "):
            raise ValueError("E_PASSWORD_MISMATCH")
        print(json.dumps(backup(args.target, args.backup, password)))
    elif args.verify_backup:
        password = getpass.getpass(messages["backupPassword"] + ": ")
        print(
            json.dumps(
                verify_database(args.verify_backup, password, args.postgres_image or "")
            )
        )
    elif args.repair:
        print(json.dumps(repair(args.target)))
    elif args.uninstall:
        purge = (
            args.delete_data
            and input(messages["deleteDataReview"] + " [DELETE-DATA]: ").strip()
            == "DELETE-DATA"
        )
        if args.delete_data and not purge:
            raise ValueError("E_CONFIRMATION")
        print(json.dumps(uninstall(args.target, purge)))
    return 0
