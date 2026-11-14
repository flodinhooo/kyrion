"""Real journals/files/crypto; frozen execution, OS ownership and scheduling injected.

Synthetic capture is explicitly not a live database or OS-start acceptance test.
"""

import copy
import datetime as dt
import hashlib
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backup_store as store
import backup_worker as worker
import recovery
from backup_policy import slot, validate
from runtime import Installation


def ordinary_output(path, _source):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


class BackupWorker(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "installed"
        self.installation = Installation(
            self.target,
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.destination = self.root / "backups"
        self.export = self.root / "recovery.key"
        raw = b"Synthetic frozen-worker identity; never executed by this test" * 2
        self.name = (
            "maintenance-"
            + hashlib.sha256(raw).hexdigest()[:32]
            + (".exe" if os.name == "nt" else "")
        )
        self.enterContext(patch("operational_restore.require_admin"))
        self.enterContext(patch.object(worker, "validate_host"))
        self.enterContext(
            patch.object(worker, "current_worker", return_value=(self.name, raw))
        )
        self.enterContext(patch.object(worker, "capability"))
        self.enterContext(patch.object(worker, "ensure_crypto"))
        self.enterContext(patch.object(store, "secure_directory"))
        self.enterContext(
            patch.object(
                store,
                "create_directory",
                side_effect=lambda path: path.mkdir(mode=0o700),
            )
        )
        self.enterContext(
            patch.object(store, "private_output", side_effect=ordinary_output)
        )
        self.enterContext(
            patch(
                "windows_security.create_private_directory",
                side_effect=lambda path: path.mkdir(mode=0o700),
            )
        )
        self.enterContext(patch("native_runtime.permissions"))
        self.scheduling = self.enterContext(
            patch(
                "backup_schedule.operate",
                return_value={"state": "registered", "coldBootVerified": False},
            )
        )
        self.capture = self.enterContext(
            patch.object(worker, "capture", side_effect=self.synthetic_capture)
        )
        self.real_verify_capture = worker.verify_capture
        self.verify = self.enterContext(
            patch.object(worker, "verify_capture", side_effect=self.synthetic_verify)
        )
        self.options = {
            "destination": self.destination,
            "export": self.export,
            "days": [1, 2, 3, 4, 5, 6, 7],
            "start": 0,
            "duration": 1440,
            "keep": 2,
            "review": lambda _: True,
        }

    def configure(self, **changes):
        return worker.configure(self.target, **{**self.options, **changes})

    def test_service_recovery_precedes_policy_and_storage_checks(self):
        self.installation.state["backupServiceRecovery"] = ["core"]
        self.installation.save()

        def restored(installation):
            installation.state.pop("backupServiceRecovery")
            installation.save()

        with patch.object(
            recovery, "recover_service_state", side_effect=restored
        ) as call:
            result = worker._run(self.installation)
        call.assert_called_once()
        self.assertFalse(result["configured"])
        self.assertNotIn("backupServiceRecoveryAttempts", self.installation.state)

    def test_service_recovery_is_bounded_and_never_crosses_update_fence(self):
        self.installation.state["backupServiceRecovery"] = ["core"]
        with patch.object(
            recovery,
            "recover_service_state",
            side_effect=ValueError("E_BACKUP_SERVICE_RECOVERY"),
        ) as call:
            for _ in range(4):
                with self.assertRaisesRegex(ValueError, "E_BACKUP_SERVICE_RECOVERY"):
                    worker._run(self.installation)
            self.assertEqual(call.call_count, 3)
            with self.assertRaisesRegex(ValueError, "E_BACKUP_SERVICE_RECOVERY"):
                worker._run(self.installation, manual=True)
            self.assertEqual(call.call_count, 4)
            self.installation.state["preparedForRestore"] = True
            self.assertTrue(worker._run(self.installation)["deferred"])
            self.assertEqual(call.call_count, 4)

    def load(self):
        return recovery.load_installation(self.target)

    def synthetic_capture(self, installation, destination, _password):
        destination.write_bytes(b"Synthetic archive payload, not GPG")

    def synthetic_verify(self, _installation, destination, _password, _configuration):
        if destination.read_bytes() != b"Synthetic archive payload, not GPG":
            raise ValueError("E_BACKUP_INTEGRITY")

    def test_rejected_configuration_creates_no_store_key_or_task(self):
        before = self.load().state
        with self.assertRaisesRegex(ValueError, "E_CONFIRMATION"):
            self.configure(review=lambda _: False)
        self.assertEqual(self.load().state, before)
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.target / store.KEY).exists())
        self.scheduling.assert_not_called()

    def test_configuration_retry_keeps_same_key_marker_revision_and_no_fake_backup(
        self,
    ):
        first = self.configure()
        saved = self.load().state
        key = (self.target / store.KEY).read_bytes()
        self.assertEqual(self.configure()["policyRevision"], first["policyRevision"])
        self.assertEqual((self.target / store.KEY).read_bytes(), key)
        self.assertEqual(self.export.read_bytes(), key)
        self.assertEqual(
            (self.destination / store.MARKER).read_bytes(),
            store.marker_bytes(self.load(), saved["backupPolicy"]["store"]["id"]),
        )
        self.assertFalse(first["backupCreated"])
        self.assertNotIn("backupHistory", self.load().state)

    def test_window_dedup_and_new_capture_never_replays_completed_slot(self):
        self.configure()
        first = worker.run(self.target)
        self.assertTrue(first["completed"])
        again = worker.run(self.target)
        self.assertTrue(again["alreadyCompletedSlot"])
        self.capture.assert_called_once()
        self.assertEqual(self.load().state["backupRun"]["attempts"], 1)

    def test_outside_window_or_disabled_never_captures(self):
        self.configure()
        with patch.object(worker, "slot", return_value=None):
            self.assertTrue(worker.run(self.target)["outsideWindow"])
        worker.disable(self.target)
        self.assertTrue(worker.run(self.target)["disabled"])
        self.capture.assert_not_called()
        self.assertTrue(self.export.exists())
        self.assertTrue((self.target / store.KEY).exists())

    def test_update_retirement_restore_and_uninstall_fences_precede_capture(self):
        self.configure()
        for field, value in (
            ("updateTransaction", {"phase": "migrating"}),
            ("authority", {}),
            ("preparedForRestore", True),
            ("stage", "uninstalled"),
        ):
            installation = self.load()
            original = copy.deepcopy(installation.state)
            installation.state[field] = value
            installation.save()
            self.assertTrue(worker.run(self.target)["deferred"])
            installation.state = original
            installation.save()
        self.capture.assert_not_called()

    def test_published_capture_resumes_verification_without_recapture_outside_window(
        self,
    ):
        self.configure()
        self.verify.side_effect = KeyboardInterrupt(
            "synthetic process loss after publication"
        )
        with self.assertRaises(KeyboardInterrupt):
            worker.run(self.target)
        self.assertEqual(self.load().state["backupRun"]["phase"], "failed")
        self.verify.side_effect = self.synthetic_verify
        with patch.object(worker, "slot", return_value=None):
            self.assertTrue(worker.run(self.target)["completed"])
        self.capture.assert_called_once()
        self.assertEqual(self.load().state["backupRun"]["attempts"], 2)

    def test_three_attempt_budget_persists_and_explicit_reset_deletes_no_files(self):
        self.configure()
        self.capture.side_effect = OSError("synthetic-private-token")
        for _attempt in range(3):
            with self.assertRaises(OSError):
                worker.run(self.target)
        before = self.load().state
        with self.assertRaisesRegex(ValueError, "E_BACKUP_SCHEDULE_ATTEMPTS"):
            worker.run(self.target)
        self.assertEqual(self.capture.call_count, 3)
        self.assertEqual(self.load().state["backupRun"]["attempts"], 3)
        self.assertNotIn("synthetic-private-token", str(self.load().state))
        with self.assertRaisesRegex(ValueError, "E_BACKUP_SCHEDULE_PENDING"):
            self.configure()
        result = worker.reset_incomplete(self.target, review=lambda _: True)
        self.assertFalse(result["filesRemoved"])
        self.assertEqual(
            self.load().state["backupAbandoned"][-1]["id"], before["backupRun"]["id"]
        )
        self.assertTrue((self.target / store.KEY).exists())

    def test_retention_never_removes_foreign_or_changed_known_file(self):
        self.configure(keep=1)
        worker.run(self.target, manual=True)
        old = self.load().state["backupHistory"][0]
        foreign = self.destination / "unrelated-user-file"
        foreign.write_bytes(b"preserve")
        (self.destination / old["name"]).write_bytes(b"modified by owner")
        with self.assertRaisesRegex(ValueError, "E_BACKUP_RETENTION_CHANGED"):
            worker.run(self.target, manual=True)
        saved = self.load().state
        self.assertEqual(saved["backupRun"]["phase"], "complete")
        self.assertEqual(saved["backupRetentionError"], "E_BACKUP_RETENTION_CHANGED")
        self.assertEqual(foreign.read_bytes(), b"preserve")
        self.assertTrue((self.destination / old["name"]).exists())

    def test_foreign_store_marker_and_key_colocation_are_refused(self):
        self.destination.mkdir()
        sentinel = self.destination / "foreign"
        sentinel.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "E_BACKUP_STORE_NOT_EMPTY"):
            self.configure()
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        sentinel.unlink()
        with self.assertRaisesRegex(ValueError, "E_BACKUP_KEY_EXPORT"):
            self.configure(export=self.destination / "recovery.key")
        self.scheduling.assert_not_called()

    def test_missing_store_marker_never_recreates_storage_during_background_run(self):
        self.configure()
        (self.destination / store.MARKER).unlink()
        with self.assertRaisesRegex(ValueError, "E_BACKUP_STORE_OWNER"):
            worker.run(self.target)
        self.assertFalse((self.destination / store.MARKER).exists())
        self.capture.assert_not_called()
        self.assertEqual(
            self.load().state["backupAttempt"]["error"], "E_BACKUP_STORE_OWNER"
        )
        self.assertFalse(self.load().state["backupAttempt"]["completed"])
        with self.assertRaisesRegex(ValueError, "E_BACKUP_STORE_OWNER"):
            self.configure()
        self.assertFalse((self.destination / store.MARKER).exists())

    def test_interrupted_marker_publication_resumes_same_owned_intent(self):
        with (
            patch.object(
                store.os,
                "link",
                side_effect=KeyboardInterrupt("before marker publication"),
            ),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.configure()
        before = self.load().state["backupStoreIntent"]
        self.assertFalse((self.destination / store.MARKER).exists())
        self.configure()
        self.assertEqual(self.load().state["backupPolicy"]["store"], before)

    def test_interrupted_key_export_preserves_the_same_key_on_retry(self):
        original = os.link

        def interrupted(source, destination, **kwargs):
            if destination == self.export:
                raise KeyboardInterrupt("before separate key export")
            return original(source, destination, **kwargs)

        with (
            patch.object(store.os, "link", side_effect=interrupted),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.configure()
        key = (self.target / store.KEY).read_bytes()
        self.assertFalse(self.export.exists())
        self.configure()
        self.assertEqual((self.target / store.KEY).read_bytes(), key)
        self.assertEqual(self.export.read_bytes(), key)

    def test_changed_known_key_is_never_silently_adopted_or_exported(self):
        self.configure()
        exported = self.export.read_bytes()
        (self.target / store.KEY).write_bytes(b"f" * 64 + b"\n")
        with self.assertRaisesRegex(ValueError, "E_BACKUP_SCHEDULE_KEY"):
            self.configure()
        self.assertEqual(self.export.read_bytes(), exported)

    def test_store_switch_and_return_preserve_other_stores_and_history(self):
        self.configure(keep=1)
        worker.run(self.target, manual=True)
        first = self.load().state["backupHistory"][0]
        alternative = self.root / "alternative-store"
        self.configure(destination=alternative, keep=1)
        worker.run(self.target, manual=True)
        worker.run(self.target, manual=True)
        self.assertTrue((self.destination / first["name"]).is_file())
        self.configure(keep=1)
        self.assertEqual(
            self.load().state["backupPolicy"]["store"]["id"], first["storeId"]
        )
        self.assertEqual(len(self.load().state["backupStores"]), 2)

    def test_normalized_paths_cannot_put_store_inside_installation(self):
        alias = self.root / "unused" / ".." / "installed" / "backups"
        with self.assertRaisesRegex(ValueError, "E_BACKUP_STORE"):
            self.configure(destination=alias)
        self.scheduling.assert_not_called()

    def test_status_does_not_call_saved_configuration_live_success_or_leak_errors(self):
        self.configure()
        self.scheduling.side_effect = ValueError("E_TASK_MISSING")
        (self.destination / store.MARKER).unlink()
        installation = self.load()
        installation.state["backupRetentionError"] = "token=private-retention-token"
        installation.state["backupAttempt"] = {
            "at": "private-token",
            "error": "password=private-password",
            "extra": "private-user",
        }
        installation.save()
        result = worker.status(self.target)
        self.assertEqual(result["schedule"]["state"], "unverified")
        self.assertFalse(result["storeAvailable"])
        self.assertTrue(result["keyAvailable"])
        self.assertNotIn("private-", str(result))

    def test_real_gpg_and_archive_verification_before_success(self):
        self.configure()
        source = self.root / "synthetic-database.dump"
        source.write_bytes(b"Synthetic DB bytes: no actual database acceptance")

        def real_crypto_capture(installation, destination, password):
            archive = self.root / "synthetic-backup.tar"
            recovery.create_archive(
                {"database.dump": source},
                {
                    "installationId": installation.state["installationId"],
                    "configuration": installation.configuration,
                    "scheduledBackupRunId": installation.state["backupRun"]["id"],
                    "postgresMajor": 17,
                },
                archive,
            )
            recovery.crypto(archive, destination, password)

        original = recovery.verified_plaintext

        def without_os_acl(*args, **kwargs):
            return original(*args, **{**kwargs, "security_source": None})

        self.capture.side_effect = real_crypto_capture
        self.verify.side_effect = self.real_verify_capture
        with patch.object(worker, "verified_plaintext", side_effect=without_os_acl):
            result = worker.run(self.target, manual=True)
        self.assertTrue(result["integrityVerified"])
        self.assertFalse(result["applicationRestoreVerified"])
        self.assertEqual(self.load().state["backupRun"]["phase"], "complete")
        first = self.load().state["backupHistory"][0]
        original_bytes = (self.destination / first["name"]).read_bytes()

        def replay_previous(_installation, destination, _password):
            destination.write_bytes(original_bytes)

        self.capture.side_effect = replay_previous
        with (
            patch.object(worker, "verified_plaintext", side_effect=without_os_acl),
            self.assertRaisesRegex(ValueError, "E_BACKUP_CAPTURE_MISMATCH"),
        ):
            worker.run(self.target, manual=True)
        self.assertEqual(len(self.load().state["backupHistory"]), 1)
        self.assertEqual(self.load().state["backupRun"]["phase"], "failed")


class BackupPolicy(unittest.TestCase):
    def value(self):
        return {
            "formatVersion": 1,
            "revision": str(uuid.uuid4()),
            "enabled": True,
            "workerFile": "maintenance-" + "a" * 32,
            "utcDays": [7],
            "startMinute": 23 * 60 + 30,
            "durationMinutes": 120,
            "keep": 7,
            "store": {
                "path": str(Path(tempfile.gettempdir()).resolve()),
                "id": str(uuid.uuid4()),
                "markerSha256": "b" * 64,
            },
            "keySha256": "c" * 64,
        }

    def test_window_crosses_week_boundary_with_exclusive_end(self):
        value = self.value()
        self.assertIsNotNone(
            slot(value, dt.datetime(2026, 11, 16, 0, 30, tzinfo=dt.timezone.utc))
        )
        self.assertIsNone(
            slot(value, dt.datetime(2026, 11, 16, 1, 30, tzinfo=dt.timezone.utc))
        )
        with self.assertRaisesRegex(ValueError, "E_BACKUP_TIME"):
            slot(
                value,
                dt.datetime(2026, 11, 16, tzinfo=dt.timezone.utc).replace(tzinfo=None),
            )

    def test_invalid_budget_window_worker_and_unknown_fields_rejected(self):
        for field, item in (
            ("enabled", "yes"),
            ("utcDays", [True]),
            ("durationMinutes", 15),
            ("keep", 0),
            ("workerFile", "../../cmd.exe"),
            ("formatVersion", True),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate({**self.value(), field: item})
        with self.assertRaises(ValueError):
            validate({**self.value(), "command": "arbitrary"})


if __name__ == "__main__":
    unittest.main()
