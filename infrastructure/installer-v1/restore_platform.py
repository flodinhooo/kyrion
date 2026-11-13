"""Fixed PostgreSQL and schema-migration operations on an owned restore target."""

from __future__ import annotations

import json
import os
import subprocess
import time
import zipfile
from pathlib import Path

from bundle import sha256, unique_object
from host import reject_links

CORE_MAIN = "dev.kyrion.core.security.OperationalRestoreAdmin"
PROPERTIES_LAUNCHER = "org.springframework.boot.loader.launch.PropertiesLauncher"


def verify_native_tools(
    installation,
    prefixes=("runtime/postgres/", "runtime/installer/", "runtime/java/", "app/core/"),
) -> None:
    from native_bundle import safe_member
    from native_roles import read_configuration
    from native_runtime import permissions

    permissions(installation.target, "verify")
    installation.verify_files()
    root = installation.target
    read_configuration(root)
    manifest = root / "native-manifest.json"
    if manifest.stat().st_size > 8 * 1024**2:
        raise ValueError("E_NATIVE_MANIFEST")
    records = json.loads(manifest.read_bytes(), object_pairs_hook=unique_object)
    found = set()
    for row in records["files"]:
        name = safe_member(row["path"])
        if not name.startswith(prefixes):
            continue
        path = root / "payload" / name
        reject_links(path)
        if (
            not path.is_file()
            or path.stat().st_size != row["bytes"]
            or sha256(path) != row["sha256"]
        ):
            raise ValueError("E_NATIVE_INTEGRITY")
        found.add(name)
    required = {
        "runtime/postgres/bin/psql.exe",
        "runtime/installer/gnupg/bin/gpg.exe",
        "runtime/installer/gnupg/bin/gpgconf.exe",
        "runtime/java/bin/java.exe",
        "app/core/core-runtime.jar",
    }
    if not {name for name in required if name.startswith(prefixes)} <= found:
        raise ValueError("E_BACKUP_RUNTIME_REQUIRED")


class Native:
    def __init__(self, installation, check_capability=True, tool_prefixes=None):
        from native_roles import read_configuration
        from native_runtime import admin_environment

        if tool_prefixes is None:
            verify_native_tools(installation)
        else:
            verify_native_tools(installation, tool_prefixes)
        self.installation = installation
        self.root = installation.target
        self.config = read_configuration(self.root)
        self.environment = admin_environment(self.root)
        self.environment["PGCLIENTENCODING"] = "UTF8"
        self.gpg = self.root / "payload/runtime/installer/gnupg/bin/gpg.exe"
        if check_capability:
            with zipfile.ZipFile(
                self.root / "payload/app/core/core-runtime.jar"
            ) as archive:
                if (
                    "BOOT-INF/classes/dev/kyrion/core/security/OperationalRestoreAdmin.class"
                    not in archive.namelist()
                ):
                    raise ValueError("E_RESTORE_CORE_UPGRADE_REQUIRED")

    def command(self, sql: str, *, stdin=None, database="kyrion") -> bytes:
        result = subprocess.run(
            [
                str(self.root / "payload/runtime/postgres/bin/psql.exe"),
                "-X",
                "-h",
                "127.0.0.1",
                "-p",
                str(self.config["ports"]["postgres"]),
                "-U",
                "kyrion",
                "-d",
                database,
                "--no-password",
                "-v",
                "ON_ERROR_STOP=1",
                "-Atc",
                sql,
            ],
            cwd=self.root,
            env=self.environment,
            stdin=stdin if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            timeout=300,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise ValueError("E_RESTORE_DATABASE")
        return result.stdout

    def copy_in(self, sql: str, path: Path) -> None:
        from portable_database import file_copy_command

        self.command(file_copy_command(sql, path))

    def service(self, role: str, start: bool) -> None:
        from native_runtime import plan_for
        from windows_service import ServiceManager

        plan = plan_for(self.installation, role)
        with (
            ServiceManager(writable=True) as scm,
            scm.opened(plan["name"], mutate=True) as handle,
        ):
            if not handle:
                raise ValueError("E_NATIVE_SERVICE_MISSING")
            if start:
                scm.demand(handle, plan)
                scm.start(handle, plan)
            else:
                scm.stop(handle, plan)
                scm.disable(handle, plan)

    def stop_application(self) -> None:
        for role in ("caddy", "web", "core"):
            self.service(role, False)

    def start_schema(self) -> None:
        from native_roles import healthy

        self.stop_application()
        self.ensure_database()
        if (
            self.command(
                "SELECT count(*) FROM pg_database WHERE datname='kyrion'",
                database="postgres",
            ).strip()
            == b"0"
        ):
            self.command("CREATE DATABASE kyrion", database="postgres")
        self.service("core", True)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if healthy(self.root, "core", self.config):
                return
            time.sleep(1)
        raise ValueError("E_RESTORE_SCHEMA_START")

    def ensure_database(self) -> None:
        self.service("postgres", True)

    def activate(self) -> None:
        from native_runtime import permissions, start_services

        permissions(self.root, "grant")
        start_services(self.installation)

    def apply_disposition(self, receipt: Path) -> None:
        from native_roles import role_plan

        executable, _, environment = role_plan(self.root, "core", self.config)
        environment["KYRION_RESTORE_TARGET_ID"] = self.installation.state[
            "installationId"
        ]
        with (self.root / "restore-admin.log").open("ab") as log:
            result = subprocess.run(
                [
                    str(executable),
                    "-Dloader.main=" + CORE_MAIN,
                    "-cp",
                    str(self.root / "payload/app/core/core-runtime.jar"),
                    PROPERTIES_LAUNCHER,
                    str(receipt),
                ],
                cwd=self.root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=120,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        if result.returncode:
            raise ValueError("E_RESTORE_SECURITY")


class Compose:
    def __init__(self, installation, check_capability=True):
        self.installation = installation
        self.root = installation.target
        self.gpg = None
        self.environment = None
        if not check_capability:
            return
        result = subprocess.run(
            [
                "docker",
                "run",
                "--pull",
                "never",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "java",
                "kyrion/core:" + installation.configuration["release"],
                "-Dloader.main=" + CORE_MAIN,
                "-cp",
                "/opt/kyrion/app.jar",
                PROPERTIES_LAUNCHER,
                "--capability",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode or len(result.stdout) > 4096:
            raise ValueError("E_RESTORE_CORE_UPGRADE_REQUIRED")
        capability = json.loads(result.stdout, object_pairs_hook=unique_object)
        if capability != {
            "formatVersion": 1,
            "coreSchema": 49,
            "coreOwnedDisposition": True,
        }:
            raise ValueError("E_RESTORE_CORE_UPGRADE_REQUIRED")

    def command(self, sql: str, *, stdin=None) -> bytes:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--project-name",
                "kyrion-" + self.installation.state["installationId"],
                "--env-file",
                str(self.root / ".env"),
                "-f",
                str(self.root / "compose.yml"),
                "exec",
                "-T",
                "postgres",
                "psql",
                "-X",
                "-U",
                "kyrion",
                "-d",
                "kyrion",
                "-v",
                "ON_ERROR_STOP=1",
                "-Atc",
                sql,
            ],
            stdin=stdin if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            timeout=300,
            check=False,
        )
        if result.returncode:
            raise ValueError("E_RESTORE_DATABASE")
        return result.stdout

    def copy_in(self, sql: str, path: Path) -> None:
        with path.open("rb") as stream:
            self.command(sql, stdin=stream)

    def stop_application(self) -> None:
        self.installation.compose("stop", "caddy", "web", "core")

    def start_schema(self) -> None:
        self.stop_application()
        for role in ("postgres", "core"):
            self.installation.compose(
                "up",
                "-d",
                "--pull",
                "never",
                "--wait",
                role,
                timeout=180,
                restore_role=role,
            )

    def ensure_database(self) -> None:
        self.installation.compose(
            "up",
            "-d",
            "--pull",
            "never",
            "--wait",
            "postgres",
            timeout=180,
            restore_role="postgres",
        )

    def activate(self) -> None:
        self.installation.start()

    def apply_disposition(self, receipt: Path) -> None:
        reject_links(receipt)
        if ":" in str(receipt) or not receipt.resolve().is_relative_to(
            self.root.resolve()
        ):
            raise ValueError("E_RESTORE_MATERIAL")
        # This receipt is public authentication metadata. The host owns it and
        # the container gets only a read-only bind; no extra Linux capability or
        # root container user is required to read original Core-owned secrets.
        receipt.chmod(0o444)
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--project-name",
                "kyrion-" + self.installation.state["installationId"],
                "--env-file",
                str(self.root / ".env"),
                "-f",
                str(self.root / "compose.yml"),
                "run",
                "--pull",
                "never",
                "--rm",
                "--no-deps",
                "-T",
                "--entrypoint",
                "java",
                "--volume",
                str(receipt) + ":/run/kyrion-restore-transfer.json:ro",
                "-e",
                "KYRION_RESTORE_TARGET_ID=" + self.installation.state["installationId"],
                "core",
                "-Dloader.main=" + CORE_MAIN,
                "-cp",
                "/opt/kyrion/app.jar",
                PROPERTIES_LAUNCHER,
                "/run/kyrion-restore-transfer.json",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode:
            raise ValueError("E_RESTORE_SECURITY")


def backend(installation, *, require_restore_capability=True):
    if installation.state.get("backend") == "windows-native":
        return Native(installation, require_restore_capability)
    if os.name != "posix" or os.geteuid() != 0:
        raise ValueError("E_PLATFORM")
    return Compose(installation, require_restore_capability)
