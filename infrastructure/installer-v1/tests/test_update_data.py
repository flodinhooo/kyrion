"""Real-file recovery and interruption checks; no OS service acceptance."""

import hashlib
import io
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bundle import sha256
from restore_material import data_owner
from runtime import Installation
from update_data import reconcile_pending, restore


class UpdateDataRecovery(unittest.TestCase):
    @unittest.skipUnless(
        os.name == "posix" and os.geteuid() == 0,
        "actual Linux UID policy needs root; Windows ACLs are separate",
    )
    def test_host_recovery_key_ownership_supports_existing_linux_host_tool(self):
        name = "recovery/741245ef-e4bf-4f01-b8e8-4f996fb3cbe6.host-key"
        self.installation.write(name, b"synthetic recovery key")
        data_owner(self.installation, name, self.root / name)
        self.assertEqual((self.root / name).stat().st_uid, 10001)
        self.assertEqual((self.root / name).stat().st_gid, 10001)
        self.assertEqual((self.root / name).stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / "recovery").stat().st_uid, 10001)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "installation"
        self.installation = Installation(
            self.root,
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.installation.write("secrets/credential.key", b"c" * 32)
        self.installation.write("secrets/audit-integrity.key", b"a" * 32)
        self.installation.write("recovery/test.json", b"newer synthetic data")
        self.directory = self.root / "transaction/test"
        self.directory.mkdir(parents=True)
        self.installation.state["updateTransaction"] = {
            "phase": "recovering-db",
            "directory": "transaction/test",
        }
        self.archive = Path(temporary.name) / "data.tar"
        raw = b"original synthetic data"
        with tarfile.open(self.archive, "w") as package:
            entry = tarfile.TarInfo("recovery/test.json")
            entry.size = len(raw)
            package.addfile(entry, io.BytesIO(raw))
        self.manifest = {
            "files": {
                name: {"sha256": sha256(self.root / name)}
                for name in ("secrets/credential.key", "secrets/audit-integrity.key")
            }
        }
        self.manifest["files"]["recovery/test.json"] = {
            "sha256": hashlib.sha256(raw).hexdigest()
        }

    def test_interrupted_publication_reconciles_hash_and_preserves_newer_bytes(self):
        original_replace = os.replace

        def cut_after_replace(source, target):
            original_replace(source, target)
            if Path(target) == self.root / "recovery/test.json":
                raise InterruptedError("synthetic power interruption")

        with (
            patch("update_data.os.replace", side_effect=cut_after_replace),
            self.assertRaises(InterruptedError),
        ):
            restore(self.installation, self.archive, self.manifest)
        self.assertIn("pendingData", self.installation.state["updateTransaction"])
        reconcile_pending(self.installation)
        self.installation.verify_files()
        restore(self.installation, self.archive, self.manifest)
        self.assertNotIn("pendingData", self.installation.state["updateTransaction"])
        retained = list(self.directory.glob("changed-*"))
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].read_bytes(), b"newer synthetic data")
        self.assertEqual(
            (self.root / "recovery/test.json").read_bytes(), b"original synthetic data"
        )

    def test_key_change_refuses_before_data_replacement(self):
        (self.root / "secrets/credential.key").write_bytes(b"different key")
        with self.assertRaisesRegex(ValueError, "E_UPDATE_KEY_CHANGED"):
            restore(self.installation, self.archive, self.manifest)
        self.assertEqual(
            (self.root / "recovery/test.json").read_bytes(), b"newer synthetic data"
        )

    def test_unexpected_pending_bytes_are_preserved_and_rejected(self):
        self.installation.state["updateTransaction"]["pendingData"] = {
            "name": "recovery/test.json",
            "old": "0" * 64,
            "new": "1" * 64,
        }
        with self.assertRaisesRegex(ValueError, "E_UPDATE_CHANGED"):
            reconcile_pending(self.installation)
        self.assertEqual(
            (self.root / "recovery/test.json").read_bytes(), b"newer synthetic data"
        )
