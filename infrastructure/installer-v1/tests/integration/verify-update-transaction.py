"""Actual Core/PG17/GPG update, interrupted switch and recovery.

Synthetic signed Windows runtime manifests contain real Core JARs. Vendor PE
fixtures never execute. OS service/ACL/installer guards use a process adapter.
This is not Windows SCM, Docker or cold-boot acceptance. Linux requires the
existing isolated network namespace and dedicated unprivileged fixture user.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import runpy
import secrets
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import authority
import native_bundle
import portable_database
import update_transaction as updater
from bundle import ReviewedBundle, sha256
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from postgres_fixture import PostgresFixture
from recovery import (
    COUNTS_SQL,
    allowed_member,
    create_archive,
    crypto,
    load_installation,
)
from runtime import Installation
from test_native_bundle import synthetic_pe
from update_database import names
from update_native import LAUNCHER, MAIN, Native

helpers = runpy.run_path(
    str(Path(__file__).with_name("verify-application-restore.py")),
    run_name="update_fixture_helpers",
)
CoreProcess, create_keys = helpers["CoreProcess"], helpers["keys"]


def public_bundle(directory, jar, release, schema):
    directory.mkdir()
    records = []
    archive = directory / "kyrion-windows-amd64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name in sorted(native_bundle.REQUIRED_FILES):
            raw = (
                jar.read_bytes()
                if name == "app/core/core-runtime.jar"
                else synthetic_pe()
                if name.endswith(".exe")
                else b"Synthetic public fixture; never executed"
            )
            package.writestr(name, raw)
            records.append(
                {
                    "path": name,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    versions = {
        "core": release,
        "web": release,
        "installer": release,
        "java": "21.0.13+9",
        "node": "22.23.3",
        "postgres": "17.11",
        "caddy": "2.10.2",
    }
    manifest = {
        "schemaVersion": 3,
        "runtime": "windows-native",
        "architecture": "windows/amd64",
        "release": release,
        "compatibility": {"api": 1, "schema": schema, "postgresMajor": 17},
        "components": {
            name: {
                "version": version,
                "sourceUrl": "https://synthetic.example.test/source",
                "license": "fixture-only",
                "licenseUrl": "https://synthetic.example.test/license",
            }
            for name, version in versions.items()
        },
        "artifact": {
            "name": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256(archive),
        },
        "files": records,
    }
    raw = json.dumps(manifest, sort_keys=True).encode()
    (directory / "manifest.json").write_bytes(raw)
    native_bundle.validate(directory)
    return ReviewedBundle(manifest, hashlib.sha256(raw).hexdigest())


def signed_inputs(installation, bundle, reviewed, *, target_schema=50):
    private = Ed25519PrivateKey.generate()
    now = int(time.time())
    trust = {
        "formatVersion": 1,
        "epoch": 1,
        "keys": [
            {
                "id": "fixture",
                "pem": private.public_key()
                .public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                .decode(),
                "notBefore": now - 60,
                "notAfter": now + 86400,
                "usages": ["release-index", "trust-rotation"],
            }
        ],
    }
    candidate = {
        "version": reviewed.manifest["release"],
        "platform": "windows/amd64",
        "minimumInstaller": "1.0.0",
        "fromSchemas": [49],
        "targetSchema": target_schema,
        "apiMin": 1,
        "apiMax": 1,
        "manifestUrl": "https://synthetic.example.test/manifest.json",
        "manifestSha256": reviewed.manifest_sha256,
        "notesUrl": "https://synthetic.example.test/notes",
        "schemaDowngradeSupported": False,
        "components": {
            name: value["version"]
            for name, value in reviewed.manifest["components"].items()
        },
    }
    index = {
        "formatVersion": 1,
        "kind": "release-index",
        "sequence": 1,
        "expiresAt": now + 3600,
        "releases": [candidate],
    }
    payload = json.dumps(index, sort_keys=True).encode()
    proof = json.dumps(
        {
            "keyId": "fixture",
            "payload": base64.b64encode(payload).decode(),
            "signature": base64.b64encode(private.sign(payload)).decode(),
        }
    ).encode()
    relative = "update-input/" + reviewed.manifest_sha256[:24]
    installation.write(
        relative + "/manifest.json", (bundle / "manifest.json").read_bytes()
    )
    installation.write(relative + "/index-" + "a" * 12 + ".json", proof)
    installation.write(
        relative + "/trust-" + "b" * 12 + ".json", json.dumps(trust).encode()
    )
    shutil.copyfile(
        bundle / reviewed.manifest["artifact"]["name"],
        installation.target / relative / reviewed.manifest["artifact"]["name"],
    )
    installation.state["updatePolicy"] = {
        "formatVersion": 1,
        "revision": str(uuid.uuid4()),
        "enabled": False,
        "feed": "https://synthetic.example.test/index.json",
        "trust": trust,
        "workerFile": "maintenance-" + "a" * 32 + (".exe" if os.name == "nt" else ""),
    }
    installation.state["updateCheck"] = {"sequence": 1}
    installation.state["updateDownload"] = {
        "formatVersion": 1,
        "phase": "verified",
        "directory": relative,
        "manifestSha256": reviewed.manifest_sha256,
        "candidate": candidate,
        "policyRevision": installation.state["updatePolicy"]["revision"],
        "indexProof": "index-" + "a" * 12 + ".json",
        "trustSnapshot": "trust-" + "b" * 12 + ".json",
    }
    installation.save()


class ProcessAdapter(Native):
    def __init__(self, installation, postgres, java):
        super().__init__(installation)
        self.postgres, self.java = postgres, java
        self.core = CoreProcess(
            installation,
            postgres,
            "kyrion",
            java,
            installation.target / "payload/app/core/core-runtime.jar",
        )
        self.fail_activation = False
        self.events = []
        self.interrupt_database_rename = False

    @property
    def gpg(self):
        return None

    @property
    def environment(self):
        return None

    def query(self, sql, *, database="kyrion"):
        result = self.postgres.query(database, sql)
        if self.interrupt_database_rename and sql.startswith(
            "ALTER DATABASE kyrion RENAME TO"
        ):
            self.interrupt_database_rename = False
            raise KeyboardInterrupt(
                "Synthetic interruption after actual database rename"
            )
        return result

    def original(self):
        return {
            "manifest": json.loads((self.root / "native-manifest.json").read_bytes()),
            "databaseBytes": int(self.query("SELECT pg_database_size('kyrion')")),
        }

    def check_host(self, _payload):
        # Fake PE/runtime service host is never executed. Actual Python fence
        # logic is exercised by CoreProcess.activate(update=True).
        return

    def admin(self, operation, *, payload=None, schema=None):
        if payload is None:
            value = self.installation.state["updateTransaction"]
            choices = [
                self.root / ("next-" + value["target"]["manifestSha256"][:8]),
                self.root / "payload",
                self.root / ("failed-" + uuid.UUID(value["id"]).hex[:8]),
            ]
            payload = next(
                selected
                for selected in choices
                if selected.is_dir()
                and self.payload_digest(selected) == value["target"]["manifestSha256"]
            )
        environment = self.core.core_environment()
        if operation != "capability":
            environment["KYRION_UPDATE_TRANSACTION_ID"] = self.installation.state[
                "updateTransaction"
            ]["id"]
            environment["KYRION_UPDATE_EXPECTED_SCHEMA"] = str(schema)
        with (self.root / "update-helper.log").open("ab") as log:
            result = subprocess.run(
                [
                    str(self.java),
                    "-Dloader.main=" + MAIN,
                    "-cp",
                    str(payload / "app/core/core-runtime.jar"),
                    LAUNCHER,
                    "--capability" if operation == "capability" else "--" + operation,
                ],
                cwd=self.root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if operation == "capability" else log,
                stderr=log,
                timeout=90,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        if result.returncode:
            raise ValueError("E_UPDATE_SECURITY")
        if (
            operation == "capability"
            and json.loads(result.stdout).get("updateProtocol") != 1
        ):
            raise ValueError("E_UPDATE_CORE_UPGRADE_REQUIRED")
        self.events.append(operation)

    def quiesce(self):
        self.core.stop_application()
        authority.require_active(self.installation.state, update=True)
        self.events.append("quiesce")

    def ensure_database(self):
        if self.query("SELECT 1", database="postgres").strip() != b"1":
            raise ValueError("E_UPDATE_DATABASE_START")

    def capture(self, destination, password):
        if self.core.child is not None and self.core.child.poll() is None:
            raise ValueError("E_FIXTURE_BACKUP_WRITER")
        with tempfile_directory(self.root) as scratch:
            snapshot, rows = portable_database.capture(
                self.query, self.export, scratch / "rows"
            )
            sources = {
                name: self.root / name
                for name in self.installation.state["files"]
                if allowed_member(name)
            }
            sources.update(rows)
            sources["install-state.json"] = self.installation.path
            for tree in (self.root / "data/knowledge", self.root / "recovery"):
                if tree.exists():
                    sources.update(
                        {
                            selected.relative_to(self.root).as_posix(): selected
                            for selected in tree.rglob("*")
                            if selected.is_file()
                        }
                    )
            metadata = {
                "installationId": self.installation.state["installationId"],
                "configuration": self.installation.configuration,
                "updateTransactionId": self.installation.state["updateTransaction"][
                    "id"
                ],
                "schema": self.schema(),
                "postgresMajor": 17,
                "capturedAt": int(time.time()),
                "verificationCounts": json.loads(self.query(COUNTS_SQL)),
                "portableDatabase": snapshot,
            }
            plain = scratch / "backup.tar"
            create_archive(sources, metadata, plain)
            crypto(plain, destination, password)
        self.events.append("encrypted-backup")

    def export(self, sql, selected, database="kyrion"):
        if os.name == "nt":
            selected.touch(exist_ok=False)
            self.query(
                portable_database.file_copy_command(sql, selected), database=database
            )
        else:
            with selected.open("xb") as stream:
                self.postgres.query(database, sql, stdout=stream)

    def verify_snapshot_rows(self, database, metadata):
        with tempfile_directory(self.root) as scratch:
            _, rows = portable_database.capture(
                lambda sql: self.query(sql, database=database),
                lambda sql, selected: self.export(sql, selected, database),
                scratch / "rows",
            )
            expected = {
                name: row["sha256"]
                for name, row in self.backup_manifest["files"].items()
                if name.startswith("database-data/")
            }
            if {name: sha256(selected) for name, selected in rows.items()} != expected:
                raise ValueError("E_UPDATE_SNAPSHOT_CHANGED")

    def maintenance(self):
        try:
            self.core.activate(update=True)
        except ValueError:
            raise ValueError("E_UPDATE_MIGRATION") from None
        self.check_maintenance()

    def check_maintenance(self):
        try:
            self.core.request("GET", "/v1/auth/setup/status")
        except HTTPError as error:
            if (
                error.code == 503
                and json.loads(error.read(4096)).get("code")
                == "OPERATIONAL_MAINTENANCE"
            ):
                return
        raise ValueError("E_UPDATE_MAINTENANCE_REQUIRED")

    def stop_application(self):
        self.core.stop_application()

    def activate(self):
        if self.fail_activation:
            self.fail_activation = False
            raise ValueError("E_FIXTURE_ACTIVATION_INTERRUPTED")
        self.core.activate(update=True)
        if self.core.request("GET", "/actuator/health").get("status") != "UP":
            raise ValueError("E_UPDATE_HEALTH")


@contextlib.contextmanager
def tempfile_directory(parent):
    import tempfile

    with tempfile.TemporaryDirectory(prefix="update-private-", dir=parent) as directory:
        yield Path(directory)


def exercise_inner(postgres_bin, java, jar, expected_digest, work, *, failing=False):
    if sha256(jar) != expected_digest:
        raise ValueError("E_FIXTURE_SOURCE_CHANGED")
    if os.name == "posix":
        runpy.run_path(str(Path(__file__).with_name("verify-linux-core.py")))[
            "isolated_namespace"
        ]()
    root = work / ("update-case-" + secrets.token_hex(8))
    root.mkdir()
    target_jar = root / "target.jar"
    shutil.copyfile(jar, target_jar)
    with zipfile.ZipFile(target_jar, "a") as package:
        migration = "CREATE TABLE update_transaction_fixture(id integer PRIMARY KEY); INSERT INTO update_transaction_fixture VALUES(1);"
        if failing:
            migration += " SELECT 1/0;"
        package.writestr(
            "BOOT-INF/classes/db/migration/V50__update_transaction_fixture.sql",
            migration,
        )
        if failing:
            package.writestr(
                "BOOT-INF/classes/db/migration/V50__update_transaction_fixture.sql.conf",
                "executeInTransaction=false\n",
            )
    source_bundle, target_bundle = root / "source-public", root / "target-public"
    source = public_bundle(source_bundle, jar, "1.1.0", 49)
    target = public_bundle(target_bundle, target_jar, "1.2.0", 50)
    installation = Installation(
        root / "installed",
        source.manifest,
        source.manifest_sha256,
        "fixture.test",
        "127.0.0.1",
    )
    installation.state["backend"] = "windows-native"
    installation.write(
        "native-manifest.json", (source_bundle / "manifest.json").read_bytes()
    )
    native_bundle._unpack_reviewed(
        source_bundle, source, installation.target / "payload"
    )
    create_keys(installation)
    installation.save()
    signed_inputs(installation, target_bundle, target)
    password = "Synthetic-update-recovery-password-123456"
    with PostgresFixture(postgres_bin) as postgres, contextlib.ExitStack() as stack:
        postgres.query("postgres", "CREATE DATABASE kyrion")
        adapter = ProcessAdapter(installation, postgres, java)
        stack.callback(adapter.core.stop_application)
        adapter.core.activate()
        credentials = {
            "username": "update-owner",
            "password": "Synthetic-local-owner-password-123456",
        }
        owner = adapter.core.request(
            "POST",
            "/v1/auth/setup",
            {
                **credentials,
                "spaceType": "BUSINESS",
                "spaceName": "Synthetic update business",
            },
            bootstrap=(installation.target / "secrets/bootstrap.secret").read_text(),
        )
        token = owner["sessionToken"]
        original_user = adapter.core.request("GET", "/v1/auth/me", token=token)
        original_space = adapter.core.request("GET", "/v1/space", token=token)
        original_identity = adapter.query(
            "SELECT id FROM installation_identity WHERE singleton"
        ).strip()
        knowledge = installation.target / "data/knowledge/synthetic.txt"
        knowledge.write_text("Original synthetic knowledge\n")
        adapter.core.stop_application()
        node = str(uuid.uuid4())
        adapter.query(
            f"INSERT INTO gateway_node(id,owner_id,display_name,hostname,credential_hash,agent_version,os_name,os_version,architecture,created_at,updated_at) VALUES('{node}','{original_user['id']}','Synthetic update node','synthetic.invalid','{'a' * 64}','fixture','fixture','fixture','amd64',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        adapter.query(
            f"INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at) SELECT gen_random_uuid(),'{node}','{original_user['id']}','synthetic.no-device','{{}}',state,CURRENT_TIMESTAMP FROM unnest(ARRAY['pending','running']) state"
        )
        adapter.query(
            f"INSERT INTO central_identity_link(user_id,issuer,subject,linked_at) VALUES('{original_user['id']}','https://identity.invalid.example.test','synthetic-update-subject',CURRENT_TIMESTAMP)"
        )
        adapter.core.activate()

        def factory(inst):
            adapter.installation = inst
            adapter.core.installation = inst
            return adapter

        original_chown = getattr(os, "chown", None)

        def fixture_chown(selected, uid, gid):
            if (
                uid != 10001
                or gid != 10001
                or not Path(selected)
                .resolve()
                .is_relative_to(installation.target.resolve())
            ):
                raise ValueError("E_FIXTURE_OWNER_SCOPE")
            original_chown(selected, os.geteuid(), os.getegid())

        stack.enter_context(patch("operational_restore.require_admin"))
        stack.enter_context(patch("update_worker.validate_host"))
        stack.enter_context(
            patch(
                "update_worker.require_worker",
                side_effect=lambda inst, _policy: inst.verify_files(),
            )
        )
        stack.enter_context(
            patch("build_identity.read_build", return_value={"version": "1.0.0"})
        )
        stack.enter_context(patch.object(updater, "backend", side_effect=factory))
        stack.enter_context(
            patch(
                "native_runtime.retire_services",
                side_effect=lambda _inst: adapter.quiesce(),
            )
        )
        stack.enter_context(patch("native_runtime.permissions"))
        if os.name == "posix":
            from runtime import atomic_json

            stack.enter_context(
                patch(
                    "update_native.atomic_json",
                    side_effect=lambda selected, value, **_options: atomic_json(
                        selected, value
                    ),
                )
            )
        if original_chown is not None:
            stack.enter_context(
                patch("update_data.os.chown", side_effect=fixture_chown)
            )
        if failing:
            try:
                updater.apply(
                    installation.target, password, review=lambda _summary: True
                )
            except ValueError as error:
                if str(error) != "E_UPDATE_MIGRATION":
                    raise
            else:
                raise ValueError("E_FIXTURE_INVALID_MIGRATION_ACCEPTED")
            if (
                adapter.query(
                    "SELECT to_regclass('public.update_transaction_fixture') IS NOT NULL"
                ).strip()
                != b"t"
            ):
                raise ValueError("E_FIXTURE_NONTRANSACTIONAL_FAILURE_MISSING")
            oid = adapter.query(
                "SELECT oid FROM pg_database WHERE datname='kyrion'",
                database="postgres",
            )
            try:
                updater.recover(
                    installation.target, "Wrong-synthetic-recovery-password"
                )
            except ValueError:
                pass
            else:
                raise ValueError("E_FIXTURE_WRONG_BACKUP_PASSWORD_ACCEPTED")
            if (
                adapter.query(
                    "SELECT oid FROM pg_database WHERE datname='kyrion'",
                    database="postgres",
                )
                != oid
            ):
                raise ValueError("E_FIXTURE_DATABASE_CHANGED_BEFORE_BACKUP_AUTH")
            adapter.interrupt_database_rename = True
            try:
                updater.resume(installation.target, password)
            except KeyboardInterrupt:
                pass
            else:
                raise ValueError("E_FIXTURE_RECOVERY_INTERRUPT_NOT_REACHED")
            recovered = updater.resume(installation.target, password)
        else:
            rename = Path.rename
            cut = {"pending": True}
            automatic = {
                "formatVersion": 1,
                "revision": str(uuid.uuid4()),
                "policyRevision": installation.state["updatePolicy"]["revision"],
                "enabled": True,
                "utcDays": list(range(1, 8)),
                "startMinute": 0,
                "durationMinutes": 60,
                "maximumDownloadBytes": 1024**3,
                # Key custody has separate real-file tests. This integration
                # passes the synthetic secret directly, never through a journal.
                "keySha256": "a" * 64,
            }
            installation.state["updatePolicy"]["enabled"] = True
            installation.state["automaticUpdatePolicy"] = automatic
            installation.save()

            def interrupted(selected, destination):
                if (
                    cut["pending"]
                    and selected.name.startswith("next-")
                    and Path(destination) == installation.target / "payload"
                ):
                    cut["pending"] = False
                    raise KeyboardInterrupt(
                        "Synthetic interruption in actual directory switch"
                    )
                return rename(selected, destination)

            with (
                patch.object(Path, "rename", interrupted),
                patch("update_automatic.in_window", return_value=True),
            ):
                try:
                    updater.apply(
                        installation.target,
                        password,
                        review=lambda _summary: True,
                        automatic=automatic,
                    )
                except KeyboardInterrupt:
                    pass
                else:
                    raise ValueError("E_FIXTURE_PAYLOAD_INTERRUPT_NOT_REACHED")
            adapter.fail_activation = True
            try:
                updater.resume(installation.target, password, automatic=automatic)
            except ValueError as error:
                if str(error) != "E_FIXTURE_ACTIVATION_INTERRUPTED":
                    raise
            else:
                raise ValueError("E_FIXTURE_ACTIVATION_INTERRUPT_NOT_REACHED")
            with patch("update_automatic.in_window", return_value=False):
                complete = updater.resume(
                    installation.target, password, automatic=automatic
                )
            if complete["phase"] != "complete" or adapter.schema() != 50:
                raise ValueError("E_FIXTURE_UPDATE_NOT_COMPLETE")
            if (
                adapter.core.request("GET", "/v1/auth/me", token=token)["id"]
                != original_user["id"]
            ):
                raise ValueError("E_FIXTURE_NORMAL_UPDATE_SESSION_LOST")
            adapter.query("INSERT INTO update_transaction_fixture VALUES(2)")
            knowledge.write_text("Changed synthetic knowledge after activation\n")
            try:
                updater.recover(installation.target, password)
            except ValueError as error:
                if str(error) != "E_UPDATE_RECOVERY_WRITES_ACK_REQUIRED":
                    raise
            else:
                raise ValueError("E_FIXTURE_WRITE_LOSS_NOT_ACKNOWLEDGED")
            recovered = updater.recover(
                installation.target, password, acknowledge_writes=True
            )
        if recovered["phase"] != "recovered" or adapter.schema() != 49:
            raise ValueError("E_FIXTURE_UPDATE_RECOVERY_FAILED")
        if (
            adapter.query(
                "SELECT id FROM installation_identity WHERE singleton"
            ).strip()
            != original_identity
        ):
            raise ValueError("E_FIXTURE_UPDATE_CHANGED_HOST_IDENTITY")
        if knowledge.read_text() != "Original synthetic knowledge\n":
            raise ValueError("E_FIXTURE_KNOWLEDGE_RECOVERY_FAILED")
        logged_in = adapter.core.request("POST", "/v1/auth/login", credentials)
        new_token = logged_in["sessionToken"]
        if (
            adapter.core.request("GET", "/v1/auth/me", token=new_token)["id"]
            != original_user["id"]
            or adapter.core.request("GET", "/v1/space", token=new_token)["id"]
            != original_space["id"]
        ):
            raise ValueError("E_FIXTURE_UPDATE_IDENTITY_LOST")
        if (
            adapter.query(
                "SELECT count(*) FROM gateway_command WHERE status='failed'"
            ).strip()
            != b"2"
        ):
            raise ValueError("E_FIXTURE_RECOVERED_COMMAND_REPLAY")
        if (
            adapter.query("SELECT subject FROM central_identity_link").strip()
            != b"synthetic-update-subject"
        ):
            raise ValueError("E_FIXTURE_UPDATE_LINK_LOST")
        if (
            adapter.query("SELECT credential_hash FROM gateway_node").strip()
            == b"a" * 64
        ):
            raise ValueError("E_FIXTURE_RECOVERED_DEVICE_CREDENTIAL_REPLAY")
        session_count = adapter.query("SELECT count(*) FROM auth_session")
        updater.resume(installation.target, password)
        if adapter.query("SELECT count(*) FROM auth_session") != session_count:
            raise ValueError("E_FIXTURE_COMPLETED_RECOVERY_REPLAY")
        value = load_installation(installation.target).state["updateTransaction"]
        failed_name = names(value)["failed"]
        if (
            adapter.query(
                "SELECT count(*) FROM pg_database WHERE datname='"
                + failed_name
                + "' AND NOT datallowconn",
                database="postgres",
            ).strip()
            != b"1"
        ):
            raise ValueError("E_FIXTURE_FAILED_DATABASE_NOT_RETAINED")
        return {
            "failingMigration": failing,
            "encryptedBackupVerified": True,
            "actualFlywayMigration": True,
            "actualDatabaseTemplateRecovery": True,
            "originalHostIdentityPreserved": True,
            "accountSpaceAndSeededLinkPreserved": True,
            "recoveredCommandsAndCredentialsRevoked": True,
            "completedRecoveryDoesNotReplay": True,
            "interruptedPayloadAndActivationResume": not failing,
            "automaticApprovalAndOutsideWindowResume": not failing,
            "interruptedDatabaseRenameResume": failing,
            "postActivationLossRequiresAcknowledgment": not failing,
            "wrongBackupPasswordDoesNotReplaceDatabase": failing,
        }


def exercise(*arguments, **options):
    # The developer Windows process has no elevated token. Keep OS ACL
    # acceptance separate; all data here is synthetic and this boundary is
    # explicitly injected, rather than weakening production ACL checks.
    with contextlib.ExitStack() as scope:
        if os.name == "nt":
            scope.enter_context(
                patch(
                    "windows_security.open_secured_file",
                    side_effect=lambda selected, _source: os.open(
                        selected, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                    ),
                )
            )
            scope.enter_context(patch("windows_security.copy_file_security"))
            scope.enter_context(
                patch(
                    "windows_security.create_private_directory",
                    side_effect=lambda selected: selected.mkdir(mode=0o700),
                )
            )
        return exercise_inner(*arguments, **options)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("postgres-bin", "java", "core-jar", "work", "report"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--core-sha256", required=True)
    args = parser.parse_args()
    cases = [
        exercise(
            args.postgres_bin.resolve(),
            args.java.resolve(),
            args.core_jar.resolve(),
            args.core_sha256,
            args.work.resolve(),
            failing=failing,
        )
        for failing in (False, True)
    ]
    result = {
        "coreJarSha256": args.core_sha256,
        "actualCorePostgreSQLAndGPG": True,
        "cases": cases,
        "lifecycleProcessAdapter": True,
        "syntheticSignedRuntimeManifests": True,
        "vendorPEFixturesExecuted": False,
        "actualSCMOrDockerAcceptance": False,
        "coldBootAccepted": False,
        "realHouseholdActions": False,
        "networkNamespaceIsolated": os.name == "posix",
    }
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
