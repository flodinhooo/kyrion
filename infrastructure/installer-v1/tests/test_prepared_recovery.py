"""Prepared recovery journal/file tests; private Windows ACL calls are mocked."""

import hashlib
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_recovery import prepare_key


class Prepared(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.space = str(uuid.uuid4())
        self.installation = SimpleNamespace(target=self.root, state={}, save=Mock())
        self.key = self.root / "recovery" / (self.space + ".host-key")
        for name, replacement in (
            ("native_recovery.permissions", Mock()),
            ("windows_security.create_private_directory", lambda path: path.mkdir()),
            (
                "windows_security.open_secured_file",
                lambda path, source: os.open(
                    path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                ),
            ),
        ):
            p = patch(name, replacement)
            p.start()
            self.addCleanup(p.stop)

    def test_prepared_key_is_journaled_before_creation_and_reused(self):
        def save():
            if self.installation.save.call_count == 1:
                self.assertFalse(self.key.exists())
                self.assertTrue(self.installation.state["recoveryKeyPending"])

        self.installation.save.side_effect = save
        self.assertEqual(prepare_key(self.installation, self.space), self.key)
        material = self.key.read_bytes()
        self.assertEqual(len(material), 43)
        self.assertEqual(
            self.installation.state["recoveryKey"]["sha256"],
            hashlib.sha256(material).hexdigest(),
        )
        self.assertFalse(self.installation.state["recoveryKeyPending"])
        self.assertEqual(
            prepare_key(self.installation, self.space).read_bytes(), material
        )

    def test_failed_initial_journal_leaves_no_key(self):
        self.installation.save.side_effect = OSError("fixture interruption")
        with self.assertRaises(OSError):
            prepare_key(self.installation, self.space)
        self.assertFalse(self.key.exists())

    def test_interrupted_creation_retries_but_completed_missing_key_does_not(self):
        self.installation.state = {
            "recoveryKey": {"spaceId": self.space, "sha256": "a" * 64},
            "recoveryKeyPending": True,
        }
        prepare_key(self.installation, self.space)
        self.key.unlink()
        with self.assertRaisesRegex(ValueError, "E_RECOVERY_KEY_MISSING"):
            prepare_key(self.installation, self.space)

    def test_foreign_key_is_never_overwritten(self):
        self.key.parent.mkdir()
        self.key.write_bytes(b"foreign material")
        with self.assertRaisesRegex(ValueError, "E_RECOVERY_EXISTING"):
            prepare_key(self.installation, self.space)
        self.assertEqual(self.key.read_bytes(), b"foreign material")
