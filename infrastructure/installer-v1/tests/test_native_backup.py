"""Native snapshot orchestration with injected SCM, not elevated OS acceptance."""

import contextlib
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_backup


class NativeBackup(unittest.TestCase):
    def setUp(self):
        self.installation = SimpleNamespace(state={}, save=MagicMock())

    def fixture(self, states=None, foreign=None, stop_failure=None, start_failure=None):
        events = []
        manager = MagicMock(
            spec=["__enter__", "__exit__", "opened", "assert_owned", "stop", "start"]
        )
        manager.__enter__.return_value = manager
        manager.opened.side_effect = lambda name, **kw: contextlib.nullcontext(name)

        def owned(handle, plan):
            events.append(("check", handle))
            if handle == foreign:
                raise ValueError("E_SERVICE_FOREIGN")
            return {"state": (states or {}).get(handle, 4)}

        def operation(kind, failure):
            def perform(handle, plan):
                events.append((kind, handle))
                if handle == failure:
                    raise ValueError("E_SERVICE_TIMEOUT")

            return perform

        manager.assert_owned.side_effect = owned
        manager.stop.side_effect = operation("stop", stop_failure)
        manager.start.side_effect = operation("start", start_failure)
        self.enterContext(
            patch.object(native_backup, "ServiceManager", return_value=manager)
        )
        self.enterContext(
            patch.object(
                native_backup, "plan_for", side_effect=lambda _, role: {"name": role}
            )
        )
        return events

    def test_success_preserves_postgres_and_initially_stopped_frontends(self):
        events = self.fixture(states={"caddy": 1})
        with native_backup.quiesce(self.installation):
            events.append(("capture", "database"))
        self.assertEqual(
            events,
            [("check", role) for role in native_backup.ROLES]
            + [
                ("stop", "web"),
                ("stop", "core"),
                ("capture", "database"),
                ("start", "core"),
                ("start", "web"),
            ],
        )

    def test_capture_failure_restarts_all_original_frontends(self):
        events = self.fixture()
        with (
            self.assertRaisesRegex(ValueError, "capture failed"),
            native_backup.quiesce(self.installation),
        ):
            raise ValueError("capture failed")
        self.assertEqual(
            [role for action, role in events if action == "start"],
            ["core", "web", "caddy"],
        )

    def test_stop_timeout_also_attempts_original_service_restart(self):
        events = self.fixture(stop_failure="web")
        with (
            self.assertRaisesRegex(ValueError, "E_SERVICE_TIMEOUT"),
            native_backup.quiesce(self.installation),
        ):
            self.fail("capture must not start")
        self.assertEqual(
            [role for action, role in events if action == "start"], ["web", "caddy"]
        )

    def test_restart_failure_attempts_remaining_services_and_is_reported(self):
        events = self.fixture(start_failure="core")
        with (
            self.assertRaisesRegex(ValueError, "E_BACKUP_SERVICE_RECOVERY"),
            native_backup.quiesce(self.installation),
        ):
            pass
        self.assertEqual(
            [role for action, role in events if action == "start"],
            ["core", "web", "caddy"],
        )

    def test_foreign_or_invalid_initial_state_causes_no_stops(self):
        for options in (
            {"foreign": "web"},
            {"states": {"core": 2}},
            {"states": {"postgres": 1}},
            {"states": {"core": 1}},
        ):
            with self.subTest(options=options):
                events = self.fixture(**options)
                with (
                    self.assertRaises(ValueError),
                    native_backup.quiesce(self.installation),
                ):
                    self.fail("invalid initial state")
                self.assertFalse(
                    any(action in {"stop", "start"} for action, _ in events)
                )

    def test_capture_archives_original_keys_but_excludes_live_database_and_payload(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "installation"
            root.mkdir()
            files = {}
            for name in (
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
                "identity-provider.json",
                "installer.exe",
            ):
                path = root / name
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_bytes(b"synthetic original managed material")
                files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            state = {"files": files, "installationId": "synthetic-installation"}
            journal = root / "install-state.json"
            journal.write_text(json.dumps(state))
            records = []
            for name in (
                "runtime/postgres/bin/psql.exe",
                "runtime/postgres/bin/pg_dump.exe",
                "runtime/installer/gnupg/bin/gpg.exe",
                "runtime/installer/gnupg/bin/gpgconf.exe",
            ):
                path = root / "payload" / name
                path.parent.mkdir(exist_ok=True, parents=True)
                path.write_bytes(b"public test tool; never executed")
                records.append(
                    {
                        "path": name,
                        "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
            (root / "native-manifest.json").write_text(json.dumps({"files": records}))
            installation = SimpleNamespace(
                target=root,
                path=journal,
                state=state,
                configuration={"release": "1.2.3"},
                verify_files=MagicMock(),
                save=MagicMock(),
            )
            config = {
                "hostname": "fixture.test",
                "address": "127.0.0.1",
                "ports": {"postgres": 5432},
            }
            events = self.fixture()
            destination = Path(directory) / "backup.gpg"
            observed = {}

            def execute(arguments, **options):
                if arguments[0].endswith("pg_dump.exe"):
                    options["stdout"].write(b"synthetic custom PostgreSQL dump")
                    output = None
                elif options.get("stdout") == native_backup.subprocess.PIPE:
                    output = (
                        b'{"users":1,"spaces":1,"audit":4}'
                        if "json_build_object" in arguments[-1]
                        else b"49\n"
                    )
                return SimpleNamespace(returncode=0, stdout=output)

            def encrypt(source, target, password, **options):
                observed.update(native_backup.inspect_archive(source))
                self.assertEqual(
                    [role for action, role in events if action == "start"],
                    ["core", "web", "caddy"],
                )
                target.write_bytes(
                    b"synthetic encrypted result; crypto separately tested"
                )

            def secured(path, source):
                return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

            with (
                patch.object(native_backup, "read_configuration", return_value=config),
                patch.object(native_backup, "preflight"),
                patch.object(native_backup, "permissions"),
                patch.object(native_backup, "admin_environment", return_value={}),
                patch.object(
                    native_backup,
                    "create_private_directory",
                    side_effect=lambda path: path.mkdir(),
                ),
                patch.object(native_backup, "open_secured_file", side_effect=secured),
                patch("windows_security.open_secured_file", side_effect=secured),
                patch.object(
                    native_backup.subprocess, "CREATE_NO_WINDOW", 0, create=True
                ),
                patch.object(native_backup.subprocess, "run", side_effect=execute),
                patch.object(native_backup, "crypto", side_effect=encrypt),
            ):
                receipt = native_backup.capture(
                    installation, destination, "Synthetic-backup-password-123456"
                )
            self.assertTrue(receipt["integrityVerified"])
            self.assertFalse(receipt["restoreVerified"])
            self.assertIn("secrets/credential.key", observed["files"])
            self.assertIn("identity-provider.json", observed["files"])
            self.assertNotIn("installer.exe", observed["files"])
            self.assertEqual(observed["metadata"]["schema"], 49)
            self.assertFalse(list(root.glob(".backup-*")))
            self.assertEqual(installation.save.call_count, 3)

    def test_previous_interruption_restores_original_services_before_new_capture(self):
        self.installation.state["backupServiceRecovery"] = ["core", "web"]
        events = self.fixture(states={"core": 1, "web": 1, "caddy": 1})
        with native_backup.quiesce(self.installation):
            self.assertEqual(
                self.installation.state["backupServiceRecovery"], ["core", "web"]
            )
        self.assertEqual(events[4:6], [("start", "core"), ("start", "web")])
        self.assertNotIn("backupServiceRecovery", self.installation.state)

    def test_failed_service_recovery_retains_durable_obligation(self):
        self.fixture(start_failure="core")
        with (
            self.assertRaisesRegex(ValueError, "E_BACKUP_SERVICE_RECOVERY"),
            native_backup.quiesce(self.installation),
        ):
            pass
        self.assertEqual(
            self.installation.state["backupServiceRecovery"], ["core", "web", "caddy"]
        )
