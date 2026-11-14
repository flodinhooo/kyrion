"""Injected database boundaries, not native service acceptance."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_verify_backup as verify


class VerificationCleanup(unittest.TestCase):
    def setUp(self):
        self.name = "kyrion_verify_" + "a" * 32
        self.installation = SimpleNamespace(state={}, save=Mock())
        self.platform = Mock()

    def test_live_or_malformed_names_never_reach_database(self):
        for name in ("kyrion", "postgres", "kyrion_verify_../", self.name + "'", None):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(ValueError, "E_BACKUP_VERIFICATION_JOURNAL"),
            ):
                verify.database_oid(self.platform, name)
        self.platform.command.assert_not_called()

    def test_only_acknowledged_matching_oid_can_be_dropped(self):
        self.installation.state["backupVerification"] = {
            "database": self.name,
            "oid": 1234,
        }
        self.platform.command.return_value = b"1234\n"
        verify.cleanup(self.installation, self.platform)
        self.assertEqual(
            self.platform.command.call_args.args[0],
            'DROP DATABASE "' + self.name + '" WITH (FORCE)',
        )
        self.assertEqual(self.platform.command.call_args.kwargs["database"], "postgres")
        self.assertNotIn("backupVerification", self.installation.state)
        self.installation.save.assert_called_once()

    def test_unacknowledged_or_replaced_database_is_never_dropped(self):
        for pending in ({"database": self.name}, {"database": self.name, "oid": 888}):
            with self.subTest(pending=pending):
                self.platform.reset_mock()
                self.platform.command.return_value = b"1234\n"
                self.installation.state["backupVerification"] = pending
                with self.assertRaisesRegex(
                    ValueError, "E_BACKUP_VERIFICATION_AMBIGUOUS"
                ):
                    verify.cleanup(self.installation, self.platform)
                self.assertEqual(self.platform.command.call_count, 1)
                self.assertEqual(self.installation.state["backupVerification"], pending)

    def test_absent_database_acknowledges_interrupted_cleanup(self):
        self.installation.state["backupVerification"] = {
            "database": self.name,
            "oid": 1234,
        }
        self.platform.command.return_value = b""
        verify.cleanup(self.installation, self.platform)
        self.assertEqual(self.platform.command.call_count, 1)
        self.assertNotIn("backupVerification", self.installation.state)

    def test_invalid_oid_or_journal_stops_before_cleanup(self):
        for value in (True, -1, 0, "1234", 2**32):
            self.installation.state["backupVerification"] = {
                "database": self.name,
                "oid": value,
            }
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "E_BACKUP_VERIFICATION_JOURNAL"),
            ):
                verify.cleanup(self.installation, self.platform)
        self.platform.command.assert_not_called()

    def test_failed_drop_keeps_recovery_obligation(self):
        self.installation.state["backupVerification"] = {
            "database": self.name,
            "oid": 1234,
        }
        self.platform.command.side_effect = [b"1234", ValueError("E_RESTORE_DATABASE")]
        with self.assertRaisesRegex(ValueError, "E_RESTORE_DATABASE"):
            verify.cleanup(self.installation, self.platform)
        self.assertIn("backupVerification", self.installation.state)
        self.installation.save.assert_not_called()

    def test_inactive_authority_cannot_start_verification_or_cleanup(self):
        for state in (
            {"authority": {"status": "retired"}},
            {"preparedForRestore": True},
        ):
            self.installation.state = state
            with (
                self.subTest(state=state),
                patch.object(verify, "cleanup") as cleanup,
                self.assertRaisesRegex(ValueError, "E_AUTHORITY_INACTIVE"),
            ):
                verify.verify_loaded(
                    self.installation, Path("unused"), "unused", self.platform
                )
            cleanup.assert_not_called()
        self.platform.command.assert_not_called()
