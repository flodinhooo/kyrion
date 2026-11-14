"""Guided review boundaries; downloads/OS/data mutation explicitly injected."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance


class RestorePreparation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.backup = self.root / "backup.gpg"
        self.backup.write_bytes(b"Synthetic encrypted-archive stand-in; never restored")
        self.digest = hashlib.sha256(self.backup.read_bytes()).hexdigest()
        self.args = SimpleNamespace(
            target=self.root / "installed",
            bundle=self.root / "download",
            public_key=None,
            restore=self.backup,
            transfer_receipt=None,
            restore_hostname="fixture.test",
            restore_address="10.231.0.1",
        )
        self.messages = json.loads(
            (Path(maintenance.__file__).parent / "locales/en.json").read_bytes()
        )
        self.enterContext(patch("builtins.print"))
        self.inputs = self.enterContext(
            patch("builtins.input", side_effect=["MAINTAIN", "RESTORE-TO-NEW-TARGET"])
        )
        self.enterContext(
            patch("getpass.getpass", return_value="Synthetic-recovery-password-123")
        )
        self.enterContext(
            patch("host.inventory", return_value={"architecture": "amd64"})
        )
        self.preflight = self.enterContext(
            patch(
                "native_runtime.preflight" if os.name == "nt" else "runtime.preflight"
            )
        )
        self.authority = object()
        self.download = self.enterContext(
            patch(
                "install_download.interactive",
                return_value=(self.args.bundle, self.authority),
            )
        )
        self.enterContext(
            patch(
                "native_bundle.authenticated_review"
                if os.name == "nt"
                else "bundle.authenticated_review",
                return_value=SimpleNamespace(
                    manifest_sha256="a" * 64, manifest={"release": "1.0.0"}
                ),
            )
        )
        self.prepare = self.enterContext(patch("linux_runtime.interactive"))
        # Stop at the real restore entrypoint; never manufacture restored data.
        self.restore = self.enterContext(
            patch(
                "operational_restore.restore",
                side_effect=ValueError("E_TEST_RESTORE_ENTRY"),
            )
        )

    def run_to_entry(self):
        with self.assertRaisesRegex(ValueError, "E_TEST_RESTORE_ENTRY"):
            maintenance.run(self.args, self.messages)

    def test_channel_authority_and_exact_backup_reach_existing_restore(self):
        self.run_to_entry()
        self.preflight.assert_called_once()
        self.download.assert_called_once_with(
            self.args.target,
            ("windows/" if os.name == "nt" else "linux/") + "amd64",
            self.messages,
        )
        self.assertIs(self.restore.call_args.args[2], self.authority)
        self.assertEqual(self.restore.call_args.kwargs["expected_backup"], self.digest)
        if os.name == "posix":
            self.assertEqual(
                self.prepare.call_args.kwargs["restore_request"],
                {"backupSha256": self.digest},
            )
        else:
            self.prepare.assert_not_called()

    def test_declined_restore_performs_no_package_or_data_mutation(self):
        self.inputs.side_effect = ["MAINTAIN", "CANCEL"]
        with self.assertRaisesRegex(ValueError, "E_CONFIRMATION"):
            maintenance.run(self.args, self.messages)
        self.prepare.assert_not_called()
        self.restore.assert_not_called()
        self.assertFalse(self.args.target.exists())

    def test_backup_changed_during_password_prompt_refuses_preparation(self):
        def changed(*_args):
            self.backup.write_bytes(b"Changed after review")
            return "Synthetic-recovery-password-123"

        with (
            patch("getpass.getpass", side_effect=changed),
            self.assertRaisesRegex(ValueError, "E_REVIEW_CHANGED"),
        ):
            maintenance.run(self.args, self.messages)
        self.prepare.assert_not_called()
        self.restore.assert_not_called()

    def test_preflight_failure_precedes_release_download(self):
        self.preflight.side_effect = ValueError("E_PLATFORM")
        with self.assertRaisesRegex(ValueError, "E_PLATFORM"):
            maintenance.run(self.args, self.messages)
        self.download.assert_not_called()
        self.prepare.assert_not_called()
        self.restore.assert_not_called()
