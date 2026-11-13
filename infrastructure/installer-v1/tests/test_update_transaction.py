"""Real journal/config checkpoints; SQL, authorization and OS lifecycle injected.

These tests do not stand in for the real Core/PostgreSQL integration runner.
"""

import contextlib
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_transaction as updater
from authority import require_active
from bundle import ReviewedBundle, sha256
from recovery import load_installation
from runtime import Installation
from update_gate import role_mode


class UpdateTransactions(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "installation"
        installation = Installation(
            self.root,
            {"release": "1.1.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        for name, content in {
            ".env": b"KYRION_RELEASE=1.1.0\n",
            "compose.yml": b"source configuration\n",
            "secrets/credential.key": b"a" * 32,
            "secrets/audit-integrity.key": b"b" * 32,
        }.items():
            installation.write(name, content)
        installation.state["updatePolicy"] = {
            "trust": {"fixture": "injected authorization"}
        }
        installation.state["updateDownload"] = {
            "candidate": {"version": "1.2.0", "targetSchema": 50},
            "directory": "update-input/" + "b" * 24,
        }
        installation.save()
        self.events = []
        self.schema = 49
        self.migration_failure = False
        self.activation_failure = False
        fixture = self

        class Adapter:
            gpg = None
            environment = None

            def schema(self):
                return fixture.schema

            def original(self):
                return {"databaseBytes": 1}

            def identity(self):
                return {"host": "synthetic", "users": "unchanged"}

            def stage(self, *_args):
                return {
                    ".env": b"KYRION_RELEASE=1.2.0\n",
                    "compose.yml": b"target configuration\n",
                }

            def quiesce(self):
                with fixture.assertRaisesRegex(ValueError, "E_UPDATE_IN_PROGRESS"):
                    require_active(self.installation.state)
                fixture.events.append("quiesce")

            def admin(self, operation, **_args):
                fixture.events.append(operation)

            def verify_snapshot_rows(self, *_args):
                fixture.events.append("rows-checked")

            def switch(self, kind):
                fixture.events.append("switch-" + kind)

            def maintenance(self):
                fixture.assertTrue(role_mode(self.installation.state, "core"))
                fixture.schema = 50
                if fixture.migration_failure:
                    raise ValueError("E_FIXTURE_MIGRATION")

            def stop_application(self):
                fixture.events.append("stop")

            def ensure_database(self):
                pass

            def activate(self):
                fixture.assertFalse(role_mode(self.installation.state, "core"))
                fixture.events.append("activate")
                if fixture.activation_failure:
                    raise ValueError("E_FIXTURE_ACTIVATION")

        self.adapter = Adapter()

        def factory(inst):
            self.adapter.installation = inst
            return self.adapter

        self.enterContext(patch.object(updater, "backend", side_effect=factory))
        self.enterContext(patch("operational_restore.require_admin"))
        self.enterContext(patch("update_worker.validate_host"))
        self.enterContext(
            patch("build_identity.read_build", return_value={"version": "1.0.0"})
        )
        self.enterContext(
            patch(
                "update_download.revalidate",
                return_value=ReviewedBundle(
                    {"release": "1.2.0", "artifacts": []}, "b" * 64
                ),
            )
        )
        self.enterContext(patch.object(updater, "_inputs"))
        self.enterContext(
            patch.object(
                updater.shutil,
                "disk_usage",
                return_value=SimpleNamespace(free=100 * 1024**3),
            )
        )
        self.enterContext(
            patch(
                "update_database.snapshot",
                side_effect=lambda *_: self.events.append("snapshot"),
            )
        )

        def backup(inst, platform, _password, name="backup.gpg"):
            selected = updater.path(inst, name)
            if not selected.exists():
                selected.write_bytes(b"synthetic ciphertext; crypto boundary injected")
                self.events.append("backup-" + name)
            platform.backup_manifest = {
                "files": {
                    key: {"sha256": sha256(self.root / key)}
                    for key in ("secrets/credential.key", "secrets/audit-integrity.key")
                }
            }
            inst.state["updateTransaction"]["backupSha256"] = sha256(selected)
            inst.save()
            return {"portableDatabase": {}, "verificationCounts": {}}

        self.enterContext(patch.object(updater, "_backup", side_effect=backup))

    def apply(self):
        return updater.apply(
            self.root, "Synthetic-password-for-tests-only", review=lambda _: True
        )

    def test_complete_transaction_and_completed_resume_preserve_live_data(self):
        result = self.apply()
        self.assertTrue(result["complete"])
        self.assertEqual(result["phase"], "complete")
        self.assertEqual(self.events.count("prepare"), 1)
        self.assertLess(
            self.events.index("backup-backup.gpg"), self.events.index("switch-target")
        )
        self.assertLess(self.events.index("completed"), self.events.index("activate"))
        before = list(self.events)
        updater.resume(self.root, "Synthetic-password-for-tests-only")
        self.assertEqual(before, self.events)
        self.assertEqual(load_installation(self.root).configuration["release"], "1.2.0")

    def test_failed_migration_keeps_fence_and_resumes_without_duplicate_backup(self):
        self.migration_failure = True
        with self.assertRaisesRegex(ValueError, "E_FIXTURE_MIGRATION"):
            self.apply()
        state = load_installation(self.root).state
        self.assertEqual(state["updateTransaction"]["phase"], "migrating")
        with self.assertRaisesRegex(ValueError, "E_UPDATE_IN_PROGRESS"):
            require_active(state)
        self.migration_failure = False
        result = updater.resume(self.root, "Synthetic-password-for-tests-only")
        self.assertTrue(result["complete"])
        self.assertEqual(self.events.count("backup-backup.gpg"), 1)
        self.assertEqual(self.events.count("snapshot"), 1)

    def test_identity_loss_blocks_activation_after_healthy_migration(self):
        with (
            patch.object(
                self.adapter,
                "identity",
                side_effect=[
                    {"host": "same", "users": "before"},
                    {"host": "same", "users": "lost"},
                ],
            ),
            self.assertRaisesRegex(ValueError, "E_UPDATE_IDENTITY_CHANGED"),
        ):
            self.apply()
        self.assertNotIn("activate", self.events)
        state = load_installation(self.root).state
        self.assertEqual(state["updateTransaction"]["phase"], "checking")
        with self.assertRaisesRegex(ValueError, "E_UPDATE_IN_PROGRESS"):
            require_active(state)

    def test_activation_retry_never_reimports_or_repeats_migration(self):
        self.activation_failure = True
        with self.assertRaisesRegex(ValueError, "E_FIXTURE_ACTIVATION"):
            self.apply()
        before = list(self.events)
        self.activation_failure = False
        updater.resume(self.root, "Synthetic-password-for-tests-only")
        self.assertEqual(self.events, before + ["activate"])

    def test_recovery_after_activation_requires_explicit_loss_ack_before_stop(self):
        self.apply()
        before = list(self.events)
        with self.assertRaisesRegex(
            ValueError, "E_UPDATE_RECOVERY_WRITES_ACK_REQUIRED"
        ):
            updater.recover(self.root, "Synthetic-password-for-tests-only")
        self.assertEqual(before, self.events)

    def test_recovery_switches_original_config_and_retains_failed_data_path(self):
        self.migration_failure = True
        with self.assertRaises(ValueError):
            self.apply()

        def restore_db(*_args):
            self.schema = 49
            self.events.append("database-recovered")

        @contextlib.contextmanager
        def plaintext(*_args, **_options):
            yield self.root / "fixture.tar", {"files": {}}, self.root

        with (
            patch("update_database.recover", side_effect=restore_db),
            patch.object(updater, "verified_plaintext", plaintext),
            patch("update_data.restore"),
        ):
            result = updater.recover(self.root, "Synthetic-password-for-tests-only")
        self.assertTrue(result["recovered"])
        self.assertEqual(load_installation(self.root).configuration["release"], "1.1.0")
        self.assertEqual((self.root / ".env").read_bytes(), b"KYRION_RELEASE=1.1.0\n")
        self.assertLess(
            self.events.index("database-recovered"), self.events.index("recovered")
        )

    def test_unknown_managed_config_change_is_never_adopted_during_resume(self):
        self.migration_failure = True
        with self.assertRaises(ValueError):
            self.apply()
        before = copy.deepcopy(load_installation(self.root).state)
        (self.root / ".env").write_bytes(b"foreign data")
        with self.assertRaisesRegex(ValueError, "E_UPDATE_CHANGED"):
            updater.resume(self.root, "Synthetic-password-for-tests-only")
        self.assertEqual((self.root / ".env").read_bytes(), b"foreign data")
        self.assertEqual(
            before["updateTransaction"]["id"],
            load_installation(self.root, verify=False).state["updateTransaction"]["id"],
        )
