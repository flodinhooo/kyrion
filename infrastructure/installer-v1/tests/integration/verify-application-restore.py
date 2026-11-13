"""Real Core/SQL/GnuPG restore using a process lifecycle adapter, not SCM/Docker.

Synthetic fresh accounts/data only. No services, tasks, real providers or devices.
Linux caller must supply the same pre-isolated namespace as verify-linux-core.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import runpy
import secrets
import socket
import ssl
import subprocess
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import authority
import operational_restore
import portable_database
from crypto_support import certificate, private_tls_key
from postgres_fixture import PostgresFixture
from recovery import COUNTS_SQL, create_archive, crypto
from runtime import Installation


def resume_fixture(target, backup, password, receipt):
    if os.name != "posix":
        return operational_restore.resume(target, backup, password, receipt)
    original = os.chown

    def owned_fixture_uid(path, uid, gid):
        if (
            uid != 10001
            or gid != 10001
            or not Path(path).resolve().is_relative_to(target.target.resolve())
        ):
            raise ValueError("E_FIXTURE_OWNER_SCOPE")
        original(path, os.geteuid(), os.getegid())

    # Process tests run Core as the dedicated unprivileged fixture user. This
    # adapts only document ownership; it is not UID 10001/container acceptance.
    with patch("restore_material.os.chown", side_effect=owned_fixture_uid):
        return operational_restore.resume(target, backup, password, receipt)


class CoreProcess:
    def __init__(self, installation, postgres, database, java, jar):
        self.installation = installation
        self.root = installation.target
        self.postgres, self.database, self.java, self.jar = (
            postgres,
            database,
            java,
            jar,
        )
        self.child = None
        self.starts = 0
        self.log = None
        self.gpg = None
        self.environment = dict(postgres.environment)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        key = private_tls_key()
        (self.root / "tls.key").write_bytes(key)
        (self.root / "tls.pem").write_bytes(certificate("localhost", "127.0.0.1", key))
        self.opener = build_opener(
            ProxyHandler({}),
            HTTPSHandler(
                context=ssl.create_default_context(cafile=str(self.root / "tls.pem"))
            ),
        )

    def request(self, method, route, body=None, token=None, bootstrap=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if bootstrap:
            headers["X-Kyrion-Setup-Secret"] = bootstrap
        req = Request(
            "https://127.0.0.1:" + str(self.port) + route,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers=headers,
        )
        with self.opener.open(req, timeout=15) as response:
            raw = response.read(2 * 1024**2)
            return json.loads(raw) if raw else None

    def start_schema(self):
        self.activate(migration=True)

    def activate(self, migration=False):
        authority.require_active(self.installation.state, migration=migration)
        if self.child is not None and self.child.poll() is None:
            return
        self.starts += 1
        self.log = (self.root / "core.log").open("ab")
        environment = self.core_environment()
        self.child = subprocess.Popen(
            [str(self.java), "-jar", str(self.jar)],
            cwd=self.root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=self.log,
            stderr=self.log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for _ in range(120):
            if self.child.poll() is not None:
                raise ValueError("E_RESTORE_FIXTURE_CORE_EXIT")
            try:
                if self.request("GET", "/actuator/health").get("status") == "UP":
                    return
            except (HTTPError, URLError, OSError, TimeoutError):
                pass
            time.sleep(1)
        raise ValueError("E_RESTORE_FIXTURE_CORE_NOT_READY")

    def core_environment(self):
        return {
            **self.environment,
            "SERVER_PORT": str(self.port),
            "SERVER_SSL_ENABLED": "true",
            "SERVER_SSL_CERTIFICATE": (self.root / "tls.pem").as_uri(),
            "SERVER_SSL_CERTIFICATE_PRIVATE_KEY": (self.root / "tls.key").as_uri(),
            "SPRING_CONFIG_IMPORT": "",
            "KYRION_CORE_ADDRESS": "127.0.0.1",
            "KYRION_DATABASE_URL": f"jdbc:postgresql://127.0.0.1:{self.postgres.port}/{self.database}",
            "KYRION_DATABASE_USER": "fixture",
            "KYRION_DATABASE_PASSWORD_FILE": str(
                self.root / "secrets/postgres-password"
            ),
            "KYRION_BOOTSTRAP_SECRET_FILE": str(self.root / "secrets/bootstrap.secret"),
            "KYRION_CREDENTIAL_KEY_FILE": str(self.root / "secrets/credential.key"),
            "KYRION_AUDIT_INTEGRITY_KEY_FILE": str(
                self.root / "secrets/audit-integrity.key"
            ),
            "KYRION_KNOWLEDGE_ROOT": str(self.root / "data/knowledge"),
            "KYRION_AI_BASE_URL": "http://127.0.0.1:9",
            "KYRION_AI_CLOUD_ENABLED": "false",
            "KYRION_CENTRAL_ENABLED": "false",
            "KYRION_KNOWLEDGE_EMBEDDING_URL": "http://127.0.0.1:9",
        }

    def stop_application(self):
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=10)
        if self.log is not None:
            self.log.close()
            self.log = None

    def apply_disposition(self, receipt):
        environment = self.core_environment()
        environment["KYRION_RESTORE_TARGET_ID"] = self.installation.state[
            "installationId"
        ]
        with (self.root / "restore-cli.log").open("ab") as log:
            result = subprocess.run(
                [
                    str(self.java),
                    "-Dloader.main=dev.kyrion.core.security.OperationalRestoreAdmin",
                    "-cp",
                    str(self.jar),
                    "org.springframework.boot.loader.launch.PropertiesLauncher",
                    str(receipt),
                ],
                cwd=self.root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=90,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        if result.returncode:
            raise ValueError("E_RESTORE_SECURITY")

    def ensure_database(self):
        return None  # The fixture's private PostgreSQL process is already alive.

    def command(self, sql):
        return self.postgres.query(self.database, sql)

    def copy_in(self, sql, path):
        if os.name == "nt":
            self.command(portable_database.file_copy_command(sql, path))
        else:
            with path.open("rb") as stream:
                self.postgres.query(self.database, sql, stdin=stream)


def fixture_installation(root):
    installation = Installation(
        root,
        {"release": "0.0.0-dev.restore-fixture", "architecture": "linux/amd64"},
        "a" * 64,
        "fixture.test",
        "127.0.0.1",
    )
    return installation


def keys(installation):
    for name in ("credential.key", "audit-integrity.key"):
        installation.write("secrets/" + name, secrets.token_bytes(32))
    installation.write("secrets/bootstrap.secret", secrets.token_urlsafe(32))
    installation.write("secrets/postgres-password", "fixture")
    (installation.target / "data/knowledge").mkdir(parents=True)


def exercise(postgres_bin, java, jar, expected_digest, work):
    if hashlib.sha256(jar.read_bytes()).hexdigest() != expected_digest:
        raise ValueError("E_FIXTURE_SOURCE_CHANGED")
    if os.name == "posix":
        runpy.run_path(str(Path(__file__).with_name("verify-linux-core.py")))[
            "isolated_namespace"
        ]()
    with PostgresFixture(postgres_bin) as postgres, contextlib.ExitStack() as stack:
        source = fixture_installation(work / ("source-" + secrets.token_hex(8)))
        target = fixture_installation(work / ("target-" + secrets.token_hex(8)))
        for name in ("source", "target"):
            postgres.query("postgres", "CREATE DATABASE " + name)
        keys(source)
        source_core = CoreProcess(source, postgres, "source", java, jar)
        stack.callback(source_core.stop_application)
        source_core.activate()
        credentials = {
            "username": "restore-owner",
            "password": "Synthetic-offline-restore-password-123456",
        }
        response = source_core.request(
            "POST",
            "/v1/auth/setup",
            {
                **credentials,
                "spaceType": "BUSINESS",
                "spaceName": "Synthetic restored business",
            },
            bootstrap=(source.target / "secrets/bootstrap.secret").read_text(),
        )
        token = response["sessionToken"]
        original_user = source_core.request("GET", "/v1/auth/me", token=token)
        original_space = source_core.request("GET", "/v1/space", token=token)
        knowledge = source.target / "data/knowledge/synthetic.txt"
        knowledge.write_text("Synthetic personal knowledge, no provider or device.\n")
        source_core.stop_application()
        # The link itself is a seeded identity fixture; this test verifies its
        # preservation, not another SSO/browser-registration acceptance run.
        postgres.query(
            "source",
            "INSERT INTO central_identity_link(user_id,issuer,subject,linked_at) VALUES('"
            + original_user["id"]
            + "','https://identity.example.invalid','synthetic-restored-subject',CURRENT_TIMESTAMP)",
        )
        node_id, satellite_id = str(uuid.uuid4()), str(uuid.uuid4())
        owner = str(uuid.UUID(original_user["id"]))
        postgres.query(
            "source",
            f"INSERT INTO gateway_node(id,owner_id,display_name,hostname,credential_hash,agent_version,os_name,os_version,architecture,created_at,updated_at) VALUES('{node_id}','{owner}','Synthetic node','synthetic.invalid','{'a' * 64}','fixture','fixture','fixture','amd64',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        )
        for status in ("pending", "running"):
            postgres.query(
                "source",
                f"INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at) VALUES(gen_random_uuid(),'{node_id}','{owner}','synthetic.no-device','{{}}','{status}',CURRENT_TIMESTAMP)",
            )
        postgres.query(
            "source",
            f"INSERT INTO voice_satellite(id,owner_id,display_name,hostname,credential_hash,runtime_version,created_at,updated_at) VALUES('{satellite_id}','{owner}','Synthetic satellite','synthetic.invalid','{'b' * 64}','fixture',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        )
        postgres.query(
            "source",
            f"INSERT INTO calendar_sync_schedule(actor_id,enabled) VALUES('{owner}',true)",
        )
        postgres.query(
            "source",
            f"INSERT INTO home_assistant_device_selection(owner_id,external_id,entity_ids,control_enabled) VALUES('{owner}','synthetic-device','[]',true)",
        )
        rows = source.target / "portable-rows"

        def export(sql, path):
            if os.name == "nt":
                with path.open("xb"):
                    pass
                postgres.query("source", portable_database.file_copy_command(sql, path))
            else:
                with path.open("xb") as stream:
                    postgres.query("source", sql, stdout=stream)

        snapshot, row_files = portable_database.capture(
            source_core.command, export, rows
        )
        sources = {
            name: source.target / name
            for name in ("secrets/credential.key", "secrets/audit-integrity.key")
        }
        sources.update(row_files)
        sources["data/knowledge/synthetic.txt"] = knowledge
        metadata = {
            "installationId": source.state["installationId"],
            "configuration": source.configuration,
            "schema": 49,
            "postgresMajor": 17,
            "verificationCounts": json.loads(source_core.command(COUNTS_SQL)),
            "portableDatabase": snapshot,
        }
        archive, backup = source.target / "fixture.tar", source.target / "fixture.gpg"
        create_archive(sources, metadata, archive)
        password = "Synthetic-backup-encryption-password-123456"
        crypto(archive, backup, password)
        digest = hashlib.sha256(backup.read_bytes()).hexdigest()
        authority.prepare_restore(target, {"backupSha256": digest})
        keys(target)
        target.state["restoreRuntimePrepared"] = True
        target.save()
        target_core = CoreProcess(target, postgres, "target", java, jar)
        stack.callback(target_core.stop_application)
        with patch.object(operational_restore, "backend", return_value=target_core):
            prepared = resume_fixture(target, backup, password, None)
            if prepared.get("applicationActivated") or target_core.child is not None:
                raise ValueError("E_RESTORE_FIXTURE_PREMATURE_ACTIVATION")
            receipt = authority.retire(
                source,
                target.state["installationId"],
                digest,
                lambda _: source_core.stop_application(),
            )
            receipt_path = source.target / "receipt.json"
            authority.export_receipt(receipt_path, receipt)
            try:
                source_core.activate()
            except ValueError as error:
                if str(error) != "E_AUTHORITY_INACTIVE":
                    raise
            else:
                raise ValueError("E_RESTORE_FIXTURE_SOURCE_RESTARTED")
            real_copy = target_core.copy_in
            copied = 0

            def interrupted_copy(sql, path):
                nonlocal copied
                copied += 1
                if copied == 3:
                    raise OSError(
                        "synthetic interruption after real partial table import"
                    )
                real_copy(sql, path)

            with patch.object(target_core, "copy_in", side_effect=interrupted_copy):
                try:
                    resume_fixture(target, backup, password, receipt_path)
                except OSError:
                    pass
                else:
                    raise ValueError("E_RESTORE_FIXTURE_INTERRUPTION_NOT_REACHED")
            if (
                target.state["restore"]["phase"] != "importing"
                or target_core.starts != 1
            ):
                raise ValueError("E_RESTORE_FIXTURE_INTERRUPTION_STATE")
            try:
                target_core.activate()
            except ValueError as error:
                if str(error) != "E_AUTHORITY_INACTIVE":
                    raise
            else:
                raise ValueError("E_RESTORE_FIXTURE_PARTIAL_TARGET_ACTIVATED")
            real_disposition = target_core.apply_disposition

            def corrupt_audit(receipt):
                target_core.command(
                    "UPDATE activity_event SET summary_code='synthetic.tamper' WHERE id=(SELECT id FROM activity_event ORDER BY occurred_at LIMIT 1)"
                )
                real_disposition(receipt)

            with patch.object(
                target_core, "apply_disposition", side_effect=corrupt_audit
            ):
                try:
                    resume_fixture(target, backup, password, receipt_path)
                except ValueError as error:
                    if str(error) != "E_RESTORE_SECURITY":
                        raise
                else:
                    raise ValueError("E_RESTORE_FIXTURE_TAMPERED_AUDIT_ACCEPTED")

            def fail_audit_append(receipt):
                target_core.command(
                    "CREATE FUNCTION public.kyrion_fixture_audit_fault() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'synthetic audit fault'; END;$$; CREATE TRIGGER kyrion_fixture_audit_fault BEFORE INSERT ON activity_event FOR EACH ROW EXECUTE FUNCTION public.kyrion_fixture_audit_fault()"
                )
                try:
                    real_disposition(receipt)
                finally:
                    target_core.command(
                        "DROP TRIGGER kyrion_fixture_audit_fault ON activity_event; DROP FUNCTION public.kyrion_fixture_audit_fault()"
                    )

            with patch.object(
                target_core, "apply_disposition", side_effect=fail_audit_append
            ):
                try:
                    resume_fixture(target, backup, password, receipt_path)
                except ValueError as error:
                    if str(error) != "E_RESTORE_SECURITY":
                        raise
                else:
                    raise ValueError("E_RESTORE_FIXTURE_FAILED_AUDIT_APPEND_ACCEPTED")
            if (
                target_core.command(
                    "SELECT id::text FROM installation_identity WHERE singleton"
                )
                .strip()
                .decode()
                == target.state["installationId"]
                or target_core.command("SELECT count(*) FROM auth_session").strip()
                != b"1"
            ):
                raise ValueError("E_RESTORE_FIXTURE_DISPOSITION_NOT_ATOMIC")
            result = resume_fixture(target, backup, password, receipt_path)
            if target_core.starts != 2:
                raise ValueError("E_RESTORE_FIXTURE_MIGRATED_PARTIAL_DATA")
            if not result["applicationActivated"]:
                raise ValueError("E_RESTORE_FIXTURE_NOT_ACTIVE")
            try:
                target_core.request("GET", "/v1/auth/me", token=token)
            except HTTPError as error:
                if error.code != 401:
                    raise
            else:
                raise ValueError("E_RESTORE_FIXTURE_OLD_SESSION_ACCEPTED")
            for restart in (False, True):
                if restart:
                    target_core.stop_application()
                    target_core.activate()
                login = target_core.request("POST", "/v1/auth/login", credentials)
                restored = target_core.request(
                    "GET", "/v1/auth/me", token=login["sessionToken"]
                )
                space = target_core.request(
                    "GET", "/v1/space", token=login["sessionToken"]
                )
                if (
                    restored["id"] != original_user["id"]
                    or restored["roles"] != original_user["roles"]
                    or space["id"] != original_space["id"]
                ):
                    raise ValueError("E_RESTORE_FIXTURE_IDENTITY_CHANGED")
            if (
                target.target / "data/knowledge/synthetic.txt"
            ).read_bytes() != knowledge.read_bytes():
                raise ValueError("E_RESTORE_FIXTURE_KNOWLEDGE_CHANGED")
            if (target.target / "secrets/credential.key").read_bytes() != (
                source.target / "secrets/credential.key"
            ).read_bytes():
                raise ValueError("E_RESTORE_FIXTURE_KEY_CHANGED")
            if (
                target_core.command(
                    "SELECT id::text FROM installation_identity WHERE singleton"
                )
                .strip()
                .decode()
                != target.state["installationId"]
            ):
                raise ValueError("E_RESTORE_FIXTURE_HOST_IDENTITY")
            if (
                target_core.command(
                    "SELECT count(*) FROM gateway_command WHERE status='failed' AND error_code='RESTORED_COMMAND_REVOKED'"
                ).strip()
                != b"2"
            ):
                raise ValueError("E_RESTORE_FIXTURE_COMMAND_REPLAY_RISK")
            if (
                target_core.command(
                    "SELECT count(*) FROM home_assistant_device_selection WHERE control_enabled"
                ).strip()
                != b"0"
                or target_core.command(
                    "SELECT count(*) FROM calendar_sync_schedule WHERE enabled"
                ).strip()
                != b"0"
            ):
                raise ValueError("E_RESTORE_FIXTURE_UNREVIEWED_CONTROL")
            if (
                target_core.command("SELECT credential_hash FROM gateway_node").strip()
                == b"a" * 64
                or target_core.command(
                    "SELECT credential_hash FROM voice_satellite"
                ).strip()
                == b"b" * 64
            ):
                raise ValueError("E_RESTORE_FIXTURE_OLD_DEVICE_CREDENTIALS")
            if (
                target_core.command(
                    "SELECT count(*) FROM activity_event WHERE event_type='installation.restored'"
                ).strip()
                != b"1"
            ):
                raise ValueError("E_RESTORE_FIXTURE_SEALED_EVENT_MISSING")
            linked = target_core.command(
                "SELECT subject FROM central_identity_link WHERE user_id='"
                + original_user["id"]
                + "'"
            ).strip()
            if linked != b"synthetic-restored-subject":
                raise ValueError("E_RESTORE_FIXTURE_LINK_LOST")
            before_repeat = target_core.command("SELECT count(*) FROM auth_session")
            resume_fixture(target, backup, password, receipt_path)
            if (
                target_core.command("SELECT count(*) FROM auth_session")
                != before_repeat
            ):
                raise ValueError("E_RESTORE_FIXTURE_REPLAY_WIPED_LIVE_DATA")
        return {
            "coreJarSha256": expected_digest,
            "actualCoreAndPostgreSQL": True,
            "actualEncryptedBackup": True,
            "newTargetHostIdentity": True,
            "sourceRetirementRequired": True,
            "retiredSourceRestartDenied": True,
            "accountSpaceRolesPreserved": True,
            "seededLinkedIdentityMappingPreserved": True,
            "partialImportInterruptedAndResumed": True,
            "partialDataNeverUsedForCoreMigration": True,
            "completedReplayPreservesLiveData": True,
            "oldSessionRevoked": True,
            "offlineLoginAfterProcessRestart": True,
            "knowledgeAndOriginalKeyPreserved": True,
            "coreOwnedDisposition": True,
            "tamperedAuditBlocksActivation": True,
            "failedAuditAppendRollsBackDisposition": True,
            "sealedRestoreEventRecordedOnce": True,
            "oldGatewayVoiceCredentialsRevoked": True,
            "pendingRunningCommandsNotReplayed": True,
            "controlsAndSchedulesAwaitReview": True,
            "archivedSqlExecuted": False,
            "processLifecycleAdapter": True,
            "actualSCMOrDockerAcceptance": False,
            "networkNamespaceIsolated": os.name == "posix",
            "coldBootAccepted": False,
            "realHouseholdActions": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("postgres-bin", "java", "core-jar", "work", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--core-sha256", required=True)
    args = parser.parse_args()
    result = exercise(
        args.postgres_bin.resolve(),
        args.java.resolve(),
        args.core_jar.resolve(),
        args.core_sha256,
        args.work.resolve(),
    )
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
