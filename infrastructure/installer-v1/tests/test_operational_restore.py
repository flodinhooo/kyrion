"""Restore review/intent boundary tests; OS provisioning is not simulated success."""

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import operational_restore
from runtime import Installation


class RestoreReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "target"
        self.backup = self.root / "synthetic.gpg"
        self.backup.write_bytes(b"synthetic review-only input, never decrypted")
        self.digest = hashlib.sha256(self.backup.read_bytes()).hexdigest()
        self.enterContext(patch.object(operational_restore, "require_admin"))
        self.provision = self.enterContext(
            patch(
                "native_runtime.provision_native"
                if os.name == "nt"
                else "runtime.provision"
            )
        )

    def restore(self, **options):
        return operational_restore.restore(
            self.target,
            self.root / "bundle",
            self.root / "public.pem",
            self.backup,
            "Synthetic-password-123456",
            "fixture.test",
            "127.0.0.1",
            **options,
        )

    def test_changed_backup_is_refused_before_any_runtime_preparation(self):
        with self.assertRaisesRegex(ValueError, "E_REVIEW_CHANGED"):
            self.restore(expected_backup="b" * 64)
        self.provision.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_changed_signed_bundle_is_not_substituted_after_review(self):
        reviewed = SimpleNamespace(manifest_sha256="b" * 64)
        with (
            patch(
                "native_bundle.authenticated_review"
                if os.name == "nt"
                else "bundle.authenticated_review",
                return_value=reviewed,
            ),
            self.assertRaisesRegex(ValueError, "E_REVIEW_CHANGED"),
        ):
            self.restore(expected_manifest="a" * 64)
        self.provision.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_resume_cannot_silently_change_the_prepared_runtime(self):
        installation = Installation(
            self.target,
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        installation.state.update(
            restoreRequest={"backupSha256": self.digest}, restoreRuntimePrepared=True
        )
        installation.save()
        before = installation.path.read_bytes()
        with (
            patch(
                "native_bundle.authenticated_review"
                if os.name == "nt"
                else "bundle.authenticated_review",
                return_value=SimpleNamespace(manifest_sha256="b" * 64),
            ),
            self.assertRaisesRegex(ValueError, "E_RESTORE_REQUEST_CONFLICT"),
        ):
            self.restore()
        self.provision.assert_not_called()
        self.assertEqual(installation.path.read_bytes(), before)
