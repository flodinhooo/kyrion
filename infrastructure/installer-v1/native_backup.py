"""Bounded native-service quiescence for consistent operational backups.

This owns no account/Space data and never touches a foreign service. The caller
holds the installation lock and validates private installation permissions.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from bundle import sha256, unique_object
from host import reject_links
from native_bundle import safe_member
from native_roles import read_configuration
from native_runtime import admin_environment, permissions, plan_for, preflight
from recovery import COUNTS_SQL, allowed_member, create_archive, crypto, inspect_archive
from runtime import installation_lock
from windows_security import create_private_directory, open_secured_file
from windows_service import DEPENDENCIES, ROLES, ServiceManager


@contextmanager
def quiesce(installation):
    """Keep PostgreSQL running; restore exactly the initially running frontends.

    Validate the whole service set before the first stop. Never restart a
    previously stopped component, even when capture fails halfway through.
    Transitional states are refused rather than guessed.
    """
    with ServiceManager(writable=True) as scm:
        plans = {role: plan_for(installation, role) for role in ROLES}
        running = set()
        for role in ROLES:
            plan = plans[role]
            with scm.opened(plan["name"], mutate=True) as handle:
                if not handle:
                    raise ValueError("E_NATIVE_SERVICE_MISSING")
                status = scm.assert_owned(handle, plan)
                if status["state"] not in {1, 4}:
                    raise ValueError("E_BACKUP_SERVICE_TRANSITION")
                if status["state"] == 4:
                    running.add(role)
        if "postgres" not in running:
            raise ValueError("E_BACKUP_DATABASE_STOPPED")
        pending = installation.state.get("backupServiceRecovery")
        if pending is not None:
            if (
                not isinstance(pending, list)
                or not pending
                or any(role not in ROLES[1:] for role in pending)
                or pending != [role for role in ROLES if role in pending]
                or any(
                    not set(DEPENDENCIES[role]) <= running | set(pending)
                    for role in pending
                )
            ):
                raise ValueError("E_BACKUP_SERVICE_JOURNAL")
            for role in pending:
                plan = plans[role]
                with scm.opened(plan["name"], mutate=True) as handle:
                    if not handle:
                        raise ValueError("E_NATIVE_SERVICE_MISSING")
                    scm.start(handle, plan)
                running.add(role)
            installation.state.pop("backupServiceRecovery")
            installation.save()
        if any(not set(DEPENDENCIES[role]) <= running for role in running):
            raise ValueError("E_BACKUP_SERVICE_DEPENDENCY")
        original = [role for role in ROLES[1:] if role in running]
        if original:
            # Persist intent before any stop. A killed process/host reboot leaves
            # an explicit service-recovery obligation for the next invocation.
            installation.state["backupServiceRecovery"] = original
            installation.save()
        attempted = set()
        try:
            for role in reversed(ROLES):
                if role == "postgres" or role not in running:
                    continue
                plan = plans[role]
                with scm.opened(plan["name"], mutate=True) as handle:
                    if not handle:
                        raise ValueError("E_NATIVE_SERVICE_MISSING")
                    # Record before stopping: a timeout may follow a successful
                    # stop; finally still has to restore its original state.
                    attempted.add(role)
                    scm.stop(handle, plan)
            yield
        finally:
            failures = []
            for role in ROLES:
                if role not in attempted:
                    continue
                plan = plans[role]
                try:
                    with scm.opened(plan["name"], mutate=True) as handle:
                        if not handle:
                            raise ValueError("E_NATIVE_SERVICE_MISSING")
                        scm.start(handle, plan)
                except (OSError, ValueError):
                    failures.append(role)
            if failures:
                # Attempt every original service; never hide a restart failure
                # behind a success receipt or expose captured provider output.
                raise ValueError("E_BACKUP_SERVICE_RECOVERY") from None
            if original:
                installation.state.pop("backupServiceRecovery")
                installation.save()


def capture(installation, destination: Path, password: str) -> dict:
    from authority import require_active

    require_active(installation.state)
    root = installation.target
    config = read_configuration(root)
    preflight(
        root, config["hostname"], config["address"], fresh=False, ports=config["ports"]
    )
    permissions(root, "verify")
    installation.verify_files()
    reject_links(destination)
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError("E_BACKUP_TARGET")
    if len(password) < 16 or any(ch in password for ch in "\r\n\x00"):
        raise ValueError("E_RECOVERY_PASSWORD")
    if (root / "native-manifest.json").stat().st_size > 8 * 1024**2:
        raise ValueError("E_NATIVE_MANIFEST")
    manifest = json.loads(
        (root / "native-manifest.json").read_bytes(), object_pairs_hook=unique_object
    )
    reviewed = set()
    for item in manifest["files"]:
        name = safe_member(item["path"])
        if not name.startswith(("runtime/postgres/", "runtime/installer/")):
            continue
        path = root / "payload" / name
        reject_links(path)
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            raise ValueError("E_NATIVE_INTEGRITY")
        reviewed.add(name)
    if (
        not {
            "runtime/postgres/bin/psql.exe",
            "runtime/postgres/bin/pg_dump.exe",
            "runtime/installer/gnupg/bin/gpg.exe",
            "runtime/installer/gnupg/bin/gpgconf.exe",
        }
        <= reviewed
    ):
        raise ValueError("E_BACKUP_RUNTIME_REQUIRED")
    scratch = root / (".backup-" + uuid.uuid4().hex)
    create_private_directory(scratch)
    environment = admin_environment(root)
    connection = [
        "-h",
        "127.0.0.1",
        "-p",
        str(config["ports"]["postgres"]),
        "-U",
        "kyrion",
        "-d",
        "kyrion",
        "--no-password",
    ]

    def command(tool, arguments, output=subprocess.PIPE):
        result = subprocess.run(
            [
                str(root / "payload/runtime/postgres/bin" / tool),
                *connection,
                *arguments,
            ],
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise ValueError("E_BACKUP_DATABASE")
        return result.stdout

    try:
        with quiesce(installation):
            schema = (
                command(
                    "psql.exe",
                    [
                        "-X",
                        "-Atc",
                        "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'",
                    ],
                )
                .decode("ascii")
                .strip()
            )
            if not schema.isdigit():
                raise ValueError("E_BACKUP_SCHEMA")
            counts = json.loads(command("psql.exe", ["-X", "-Atc", COUNTS_SQL]))
            if (
                not isinstance(counts, dict)
                or set(counts) != {"users", "spaces", "audit"}
                or any(type(value) is not int or value < 0 for value in counts.values())
            ):
                raise ValueError("E_BACKUP_COUNTS")
            dump = scratch / "database.dump"
            with os.fdopen(open_secured_file(dump, scratch), "wb") as stream:
                command(
                    "pg_dump.exe", ["--format=custom", "--no-owner", "--no-acl"], stream
                )
            if not dump.stat().st_size:
                raise ValueError("E_BACKUP_DATABASE")
            from portable_database import capture as capture_portable
            from portable_database import file_copy_command

            def export_rows(sql, path):
                # Create the protected file before psql opens it in binary mode.
                os.close(open_secured_file(path, scratch))
                command("psql.exe", ["-X", "-Atc", file_copy_command(sql, path)])

            portable, row_files = capture_portable(
                lambda sql: command("psql.exe", ["-X", "-Atc", sql]),
                export_rows,
                scratch / "database-data",
            )
            sources = {
                name: root / name
                for name in installation.state["files"]
                if allowed_member(name)
            }
            sources.update(
                {"install-state.json": installation.path, "database.dump": dump}
            )
            sources.update(row_files)
            for tree in ("data/knowledge", "recovery"):
                reject_links(root / tree)
                for path in (root / tree).rglob("*"):
                    reject_links(path)
                    if path.is_file():
                        sources[path.relative_to(root).as_posix()] = path
            required = {
                "native-runtime.json",
                "data/Caddyfile",
                "core-cert.pem",
                "web-cert.pem",
                "secrets/credential.key",
                "secrets/audit-integrity.key",
                "secrets/postgres-password",
                "secrets/pgpass",
                "secrets/core-tls.key",
                "data/tls/cert.pem",
                "data/tls/key.pem",
                "data/web-tls/key.pem",
            }
            if not required <= sources.keys():
                raise ValueError("E_BACKUP_INCOMPLETE")
            metadata = {
                "backend": "windows-native",
                "capturedAt": int(time.time()),
                "installationId": installation.state["installationId"],
                "configuration": installation.configuration,
                "schema": int(schema),
                "postgresMajor": 17,
                "verificationCounts": counts,
                "restoreVerified": False,
                "portableDatabase": portable,
                "coverage": [
                    "database",
                    "managed-configuration",
                    "original-keys",
                    "tls",
                    "knowledge",
                ],
                "excluded": [
                    "public-runtime-payload",
                    "live-database-files",
                    "external-provider-state",
                    "foreign-ollama",
                ],
            }
            if any(name.startswith("recovery/") for name in sources):
                metadata["coverage"].append("host-recovery-material")
            archive = scratch / "backup.tar"
            create_archive(sources, metadata, archive, security_source=scratch)
            inspect_archive(archive)
        # Service downtime ends before encryption. Publish only complete output,
        # using a no-overwrite hardlink on the destination volume.
        encrypted = destination.with_name(
            "." + destination.name + "." + uuid.uuid4().hex
        )
        try:
            crypto(
                archive,
                encrypted,
                password,
                executable=root / "payload/runtime/installer/gnupg/bin/gpg.exe",
                environment=environment,
            )
            os.link(encrypted, destination)
        finally:
            encrypted.unlink(missing_ok=True)
        receipt = {
            "formatVersion": 1,
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
            "integrityVerified": True,
            "restoreVerified": False,
            "coverage": metadata["coverage"],
        }
        installation.state["backup"] = "encrypted-consistent-capture"
        installation.save()
        return receipt
    finally:
        shutil.rmtree(scratch)


def backup(target: Path, destination: Path, password: str) -> dict:
    from recovery import load_installation

    with installation_lock(target):
        installation = load_installation(target)
        if installation.state.get("backend") != "windows-native":
            raise ValueError("E_NATIVE_JOURNAL")
        return capture(installation, destination, password)
