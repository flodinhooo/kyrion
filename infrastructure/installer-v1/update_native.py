"""Native owned-service update adapter; no arbitrary process/service commands."""

from __future__ import annotations

import json
import ssl
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

from bundle import sha256, unique_object
from host import reject_links
from native_roles import read_configuration, role_plan
from recovery import private_restore_directory
from runtime import atomic_json
from update_state import path, transaction

MAIN = "dev.kyrion.core.security.OperationalUpdateAdmin"
LAUNCHER = "org.springframework.boot.loader.launch.PropertiesLauncher"


class Native:
    def __init__(self, installation):
        self.installation = installation
        self.root = installation.target
        self.backup_manifest = None
        self._tools = None

    @property
    def tools(self):
        from restore_platform import Native as Database

        if self._tools is None:
            self._tools = Database(
                self.installation,
                check_capability=False,
                tool_prefixes=("runtime/postgres/", "runtime/installer/"),
            )
        return self._tools

    @property
    def gpg(self):
        return self.root / "payload/runtime/installer/gnupg/bin/gpg.exe"

    @property
    def environment(self):
        from native_runtime import admin_environment

        return admin_environment(self.root)

    def query(self, sql, *, database="kyrion") -> bytes:
        return self.tools.command(sql, database=database)

    def schema(self) -> int:
        return int(
            self.query(
                "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'"
            ).strip()
        )

    def identity(self) -> dict[str, str]:
        from update_database import identity

        return identity(self)

    def original(self) -> dict:
        from restore_platform import verify_native_tools

        verify_native_tools(self.installation)
        self.check_host(self.root / "payload")
        source = json.loads(
            (self.root / "native-manifest.json").read_bytes(),
            object_pairs_hook=unique_object,
        )
        data = Path(self.query("SHOW data_directory").decode().strip()).resolve()
        if data != (self.root / "data/postgres").resolve():
            raise ValueError("E_UPDATE_DATABASE_TARGET")
        for row in source["files"]:
            target = self.root / "payload" / row["path"]
            reject_links(target)
            if (
                not target.is_file()
                or target.stat().st_size != row["bytes"]
                or sha256(target) != row["sha256"]
            ):
                raise ValueError("E_NATIVE_INTEGRITY")
        return {
            "manifest": source,
            "databaseBytes": int(self.query("SELECT pg_database_size('kyrion')")),
        }

    def stage(
        self, reviewed, directory: Path, identifier: str, original: dict
    ) -> dict[str, bytes]:
        from native_bundle import _unpack_reviewed
        from runtime import installation_lock

        if (
            reviewed.manifest["components"]["postgres"]["version"]
            != original["manifest"]["components"]["postgres"]["version"]
        ):
            raise ValueError("E_UPDATE_POSTGRES_VERSION")
        next_payload = self.root / ("next-" + reviewed.manifest_sha256[:8])
        with installation_lock(next_payload):
            _unpack_reviewed(directory, reviewed, next_payload)
        self.check_host(next_payload)
        self.admin("capability", payload=next_payload, schema=original["schema"])
        return {"native-manifest.json": (directory / "manifest.json").read_bytes()}

    def check_host(self, payload: Path) -> None:
        from windows_system import base_environment

        result = subprocess.run(
            [str(payload / "runtime/installer/kyrion-service.exe"), "--capabilities"],
            cwd=self.root,
            env=base_environment(),
            capture_output=True,
            timeout=30,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode or len(result.stdout) > 4096:
            raise ValueError("E_UPDATE_HOST_UPGRADE_REQUIRED")
        if json.loads(result.stdout) != {
            "formatVersion": 1,
            "updateProtocol": 1,
            "startupFence": True,
            "maintenanceCore": True,
        }:
            raise ValueError("E_UPDATE_HOST_UPGRADE_REQUIRED")

    def admin(self, operation: str, *, payload=None, schema=None) -> None:
        if payload is None:
            value = transaction(self.installation)
            choices = [
                self.root / ("next-" + value["target"]["manifestSha256"][:8]),
                self.root / "payload",
                self.root / ("failed-" + value["id"].replace("-", "")[:8]),
            ]
            payload = next(
                (
                    selected
                    for selected in choices
                    if selected.is_dir()
                    and self.payload_digest(selected)
                    == value["target"]["manifestSha256"]
                ),
                None,
            )
            if payload is None:
                raise ValueError("E_UPDATE_PAYLOAD_STATE")
            manifest = json.loads(
                path(self.installation, "target-config").read_bytes(),
                object_pairs_hook=unique_object,
            )
            for row in manifest["files"]:
                if (
                    row["path"].startswith(("app/core/", "runtime/java/"))
                    and sha256(payload / row["path"]) != row["sha256"]
                ):
                    raise ValueError("E_NATIVE_INTEGRITY")
        _, _, environment = role_plan(self.root, "core", read_configuration(self.root))
        if operation == "capability":
            argument = "--capability"
        else:
            value = transaction(self.installation)
            environment["KYRION_UPDATE_TRANSACTION_ID"] = value["id"]
            environment["KYRION_UPDATE_EXPECTED_SCHEMA"] = str(schema)
            argument = "--" + operation
        result = subprocess.run(
            [
                str(payload / "runtime/java/bin/java.exe"),
                "-Dloader.main=" + MAIN,
                "-cp",
                str(payload / "app/core/core-runtime.jar"),
                LAUNCHER,
                argument,
            ],
            cwd=self.root,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode or len(result.stdout) > 16384:
            raise ValueError("E_UPDATE_SECURITY")
        if operation == "capability":
            capability = json.loads(result.stdout)
            schemas = capability.get("sourceSchemas")
            if (
                capability.get("formatVersion") != 1
                or capability.get("updateProtocol") != 1
                or capability.get("maintenanceStart") is not True
                or not isinstance(schemas, list)
                or any(type(item) is not int for item in schemas)
                or schema not in schemas
            ):
                raise ValueError("E_UPDATE_CORE_UPGRADE_REQUIRED")

    def quiesce(self) -> None:
        from native_runtime import retire_services

        retire_services(self.installation)
        self.ensure_database()

    def ensure_database(self) -> None:
        self.tools.service("postgres", True)
        for _ in range(60):
            try:
                if self.query("SELECT 1", database="postgres").strip() == b"1":
                    return
            except (ValueError, OSError):
                pass
            time.sleep(1)
        raise ValueError("E_UPDATE_DATABASE_START")

    def capture(self, destination: Path, password: str):
        from native_backup import capture

        return capture(self.installation, destination, password, update=True)

    def switch(self, kind: str) -> None:
        from native_runtime import permissions, retire_services

        value = transaction(self.installation)
        active = self.root / "payload"
        old = self.root / ("old-" + value["id"].replace("-", "")[:8])
        staged = self.root / ("next-" + value["target"]["manifestSha256"][:8])
        failed = self.root / ("failed-" + value["id"].replace("-", "")[:8])
        for selected in (active, old, staged, failed):
            reject_links(selected)

        expected = value[kind]["manifestSha256"]
        already_active = active.exists() and self.payload_digest(active) == expected
        # Service definitions are fixed to payload paths, independent of version.
        # Verify and disable before touching either directory, even on retry.
        if active.exists():
            retire_services(self.installation)
        if already_active:
            pass
        elif kind == "target":
            if active.exists():
                if (
                    old.exists()
                    or self.payload_digest(active) != value["source"]["manifestSha256"]
                ):
                    raise ValueError("E_UPDATE_PAYLOAD_STATE")
                active.rename(old)
            if (
                not old.exists()
                or not staged.exists()
                or self.payload_digest(staged) != expected
            ):
                raise ValueError("E_UPDATE_PAYLOAD_STATE")
            staged.rename(active)
        else:
            if not old.exists() or self.payload_digest(old) != expected:
                raise ValueError("E_UPDATE_OLD_PAYLOAD_MISSING")
            if active.exists():
                if (
                    failed.exists()
                    or self.payload_digest(active) != value["target"]["manifestSha256"]
                ):
                    raise ValueError("E_UPDATE_PAYLOAD_STATE")
                active.rename(failed)
            old.rename(active)
        receipt = active / ".kyrion-native-payload.json"
        record = json.loads(receipt.read_bytes(), object_pairs_hook=unique_object)
        record["rootPath"] = str(active.resolve())
        atomic_json(receipt, record, security_source=active)
        permissions(self.root, "grant")
        self._tools = None

    @staticmethod
    def payload_digest(directory):
        receipt = directory / ".kyrion-native-payload.json"
        reject_links(receipt)
        if not receipt.is_file() or receipt.stat().st_size > 8 * 1024**2:
            raise ValueError("E_UPDATE_PAYLOAD_STATE")
        record = json.loads(receipt.read_bytes(), object_pairs_hook=unique_object)
        if record.get("complete") is not True:
            raise ValueError("E_UPDATE_PAYLOAD_STATE")
        return record.get("manifestSha256")

    def maintenance(self) -> None:
        self.ensure_database()
        from native_runtime import permissions

        permissions(self.root, "grant")
        self.tools.service("core", True)
        self.check_maintenance()

    def check_maintenance(self) -> None:
        from native_roles import healthy

        config = read_configuration(self.root)
        opener = build_opener(
            ProxyHandler({}),
            HTTPSHandler(
                context=ssl.create_default_context(
                    cafile=str(self.root / "core-cert.pem")
                )
            ),
        )
        for _ in range(120):
            if healthy(self.root, "core", config):
                try:
                    with opener.open(
                        "https://127.0.0.1:"
                        + str(config["ports"]["core"])
                        + "/v1/auth/setup/status",
                        timeout=10,
                    ):
                        raise ValueError("E_UPDATE_MAINTENANCE_REQUIRED")
                except HTTPError as error:
                    if (
                        error.code == 503
                        and json.loads(error.read(4096)).get("code")
                        == "OPERATIONAL_MAINTENANCE"
                    ):
                        return
                    raise ValueError("E_UPDATE_MAINTENANCE_REQUIRED") from None
            time.sleep(1)
        raise ValueError("E_UPDATE_HEALTH")

    def stop_application(self):
        self.tools.stop_application()

    def activate(self):
        from native_runtime import permissions, start_services

        permissions(self.root, "grant")
        start_services(self.installation, update=True)

    def verify_snapshot_rows(self, database, metadata):
        from portable_database import capture, file_copy_command
        from restore_material import private_output

        with private_restore_directory(self.root, self.root) as scratch:

            def export(sql, selected):
                with private_output(selected, scratch):
                    pass
                self.query(file_copy_command(sql, selected), database=database)

            _, records = capture(
                lambda sql: self.query(sql, database=database), export, scratch / "rows"
            )
            expected = {
                name: row["sha256"]
                for name, row in self.backup_manifest["files"].items()
                if name.startswith("database-data/")
            }
            if {
                name: sha256(selected) for name, selected in records.items()
            } != expected:
                raise ValueError("E_UPDATE_SNAPSHOT_CHANGED")
