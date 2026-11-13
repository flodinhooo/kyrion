"""Real atomic file replacement/partial-journal recovery, not full restore."""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restore_material import reconcile_managed, replace_managed
from runtime import Installation


class RestoreMaterial(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "target"
        self.installation = Installation(
            self.root,
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.installation.write("secrets/credential.key", b"old key; synthetic only")

    def test_replace_is_repeatable_without_rotating_original_material(self):
        value = b"restored original key; synthetic only"
        replace_managed(self.installation, "secrets/credential.key", value)
        replace_managed(self.installation, "secrets/credential.key", value)
        self.assertEqual((self.root / "secrets/credential.key").read_bytes(), value)
        self.installation.verify_files()

    def test_lost_final_save_reconciles_only_the_two_known_digests(self):
        original_save = self.installation.save
        calls = 0

        def interrupted():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic interruption after file replace")
            original_save()

        with (
            patch.object(self.installation, "save", side_effect=interrupted),
            self.assertRaises(OSError),
        ):
            replace_managed(
                self.installation, "secrets/credential.key", b"original source key"
            )
        from recovery import load_installation

        resumed = load_installation(self.root, verify=False)
        reconcile_managed(resumed)
        self.assertEqual(
            resumed.state["files"]["secrets/credential.key"],
            hashlib.sha256(b"original source key").hexdigest(),
        )

    def test_changed_or_unknown_target_file_is_never_adopted(self):
        (self.root / "secrets/credential.key").write_bytes(b"unexpected foreign change")
        with self.assertRaisesRegex(ValueError, "E_RESTORE_TARGET_CHANGED"):
            replace_managed(
                self.installation, "secrets/credential.key", b"original source key"
            )
        self.assertFalse(self.installation.state.get("restoreFileOperations"))
