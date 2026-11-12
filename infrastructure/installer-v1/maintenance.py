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


def check_updates(args) -> dict:
    from release_policy import compatible_release, fetch_document, parse, verify

    if not args.feed or args.trust_store is None:
        raise ValueError("E_UPDATE_CONFIG")
    reject_links(args.trust_store)
    with installation_lock(args.target):
        installation = load_installation(args.target)
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
        trust = parse(args.trust_store.read_bytes())
        index = verify(fetch_document(args.feed), trust, "release-index")
        previous = installation.state.get("updateCheck", {})
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
        }
        installation.state["updateCheck"] = result
        installation.save()
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
        "updatesConfigured": False,
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
    if args.diagnostics:
        diagnostic(args.target, args.diagnostics)
        print(messages["diagnosticSaved"])
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

        if input(messages["bootstrapExtendReview"] + " [EXTEND/CANCEL]: ").strip() != "EXTEND":
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
