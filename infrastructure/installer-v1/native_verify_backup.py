"""Restore binary rows into a disposable inactive database, never the live DB."""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
import zipfile
from pathlib import Path

from bundle import sha256
from operational_restore import plaintext_options, validate_backup
from portable_database import file_copy_command, restore
from recovery import COUNTS_SQL, load_installation, verified_plaintext
from restore_material import extract_rows
from runtime import installation_lock

MAIN = "dev.kyrion.core.security.BackupVerificationAdmin"
LAUNCHER = "org.springframework.boot.loader.launch.PropertiesLauncher"


class Native:
    def __init__(self, installation):
        from restore_platform import Native as Tools

        self.tools = Tools(installation, check_capability=False)
        self.installation = installation
        self.root = installation.target
        self.gpg = self.tools.gpg
        self.environment = self.tools.environment
        with zipfile.ZipFile(
            self.root / "payload/app/core/core-runtime.jar"
        ) as archive:
            if (
                "BOOT-INF/classes/" + MAIN.replace(".", "/") + ".class"
            ) not in archive.namelist():
                raise ValueError("E_BACKUP_VERIFICATION_CORE_REQUIRED")
        actual = (
            self.command("SHOW data_directory", database="postgres").decode().strip()
        )
        if Path(actual).resolve() != (self.root / "data/postgres").resolve():
            raise ValueError("E_BACKUP_VERIFICATION_CLUSTER")
        version = self.command("SHOW server_version_num", database="postgres").strip()
        if not version.isdigit() or not 170000 <= int(version) < 180000:
            raise ValueError("E_BACKUP_COMPATIBILITY")

    def command(self, sql, *, database):
        return self.tools.command(sql, database=database)

    def migrate(self, database):
        if not re.fullmatch(r"kyrion_verify_[0-9a-f]{32}", database):
            raise ValueError("E_BACKUP_VERIFICATION_JOURNAL")
        environment = dict(self.environment)
        environment["KYRION_BACKUP_VERIFICATION_DATABASE_URL"] = (
            "jdbc:postgresql://127.0.0.1:"
            + str(self.tools.config["ports"]["postgres"])
            + "/"
            + database
        )
        environment["KYRION_DATABASE_PASSWORD_FILE"] = str(
            self.root / "secrets/postgres-password"
        )
        prepare_schema(
            self.root / "payload/runtime/java/bin/java.exe",
            self.root / "payload/app/core/core-runtime.jar",
            self.root,
            environment,
        )

    def copy_in(self, database, sql, path):
        self.command(file_copy_command(sql, path), database=database)


def prepare_schema(java: Path, jar: Path, root: Path, environment: dict[str, str]):
    result = subprocess.run(
        [
            str(java),
            "-Dloader.main=" + MAIN,
            "-cp",
            str(jar),
            LAUNCHER,
            "--migrate-empty",
        ],
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=180,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        raise ValueError("E_BACKUP_VERIFICATION_SCHEMA")


def database_oid(platform, name):
    if not isinstance(name, str) or not re.fullmatch(
        r"kyrion_verify_[0-9a-f]{32}", name
    ):
        raise ValueError("E_BACKUP_VERIFICATION_JOURNAL")
    value = platform.command(
        "SELECT oid FROM pg_database WHERE datname='" + name + "'", database="postgres"
    ).strip()
    if value and (not value.isdigit() or not 0 < int(value) < 2**32):
        raise ValueError("E_BACKUP_VERIFICATION_JOURNAL")
    return int(value) if value else None


def cleanup(installation, platform):
    pending = installation.state.get("backupVerification")
    if pending is None:
        return
    if (
        not isinstance(pending, dict)
        or set(pending) not in ({"database"}, {"database", "oid"})
        or (
            "oid" in pending
            and (type(pending["oid"]) is not int or not 0 < pending["oid"] < 2**32)
        )
    ):
        raise ValueError("E_BACKUP_VERIFICATION_JOURNAL")
    name = pending["database"]
    actual = database_oid(platform, name)
    if actual is not None:
        if "oid" not in pending or actual != pending["oid"]:
            raise ValueError("E_BACKUP_VERIFICATION_AMBIGUOUS")
        platform.command(
            'DROP DATABASE "' + name + '" WITH (FORCE)', database="postgres"
        )
    installation.state.pop("backupVerification")
    installation.save()


def verify_loaded(installation, source, password, platform):
    """Caller owns the installation lock and has verified the native cluster."""
    from authority import require_active

    require_active(installation.state)
    cleanup(installation, platform)
    digest = sha256(source)
    with verified_plaintext(
        source, password, **plaintext_options(installation, platform)
    ) as (archive, manifest, scratch):
        metadata = validate_backup(manifest, installation, allow_same_identity=True)
        if sha256(source) != digest:
            raise ValueError("E_BACKUP_INTEGRITY")
        rows = extract_rows(archive, manifest, scratch)
        name = "kyrion_verify_" + uuid.uuid4().hex
        if database_oid(platform, name) is not None:
            raise ValueError("E_BACKUP_VERIFICATION_AMBIGUOUS")
        installation.state["backupVerification"] = {"database": name}
        installation.save()
        try:
            platform.command(
                'CREATE DATABASE "' + name + '" TEMPLATE template0', database="postgres"
            )
            oid = database_oid(platform, name)
            if oid is None:
                raise ValueError("E_BACKUP_VERIFICATION_DATABASE")
            installation.state["backupVerification"]["oid"] = oid
            installation.save()
            platform.migrate(name)

            def query(sql):
                return platform.command(sql, database=name)

            restore(
                query,
                query,
                lambda sql, path: platform.copy_in(name, sql, path),
                metadata["portableDatabase"],
                rows,
            )
            counts = json.loads(query(COUNTS_SQL))
            if counts != metadata["verificationCounts"]:
                raise ValueError("E_RESTORE_COUNTS")
        finally:
            cleanup(installation, platform)
    result = {
        "backupSha256": digest,
        "integrityVerified": True,
        "restoreVerified": True,
        "verificationOnly": True,
        "liveDatabaseReplaced": False,
        "applicationServicesStarted": False,
        "schema": metadata["schema"],
        "counts": counts,
    }
    installation.state["lastBackupVerification"] = result
    installation.save()
    return result


def verify(target: Path, source: Path, password: str):
    with installation_lock(target):
        installation = load_installation(target)
        from authority import require_active

        require_active(installation.state)
        if installation.state.get("backend") != "windows-native":
            raise ValueError("E_NATIVE_PLATFORM")
        return verify_loaded(installation, source, password, Native(installation))
