"""Real protected-file metadata/journal tests with isolated Core-state responses."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap_maintenance as bootstrap
from recovery import load_installation
from runtime import Installation


class BootstrapWindow(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "installation"
        self.installation = Installation(
            self.root,
            {"release": "1.2.3", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.installation.write("secrets/bootstrap.secret", "b" * 43 + "\n")
        self.path = self.root / "secrets/bootstrap.secret"
        os.utime(self.path, (time.time() - 1900, time.time() - 1900))
        host = patch.object(bootstrap, "authorize_host")
        self.host = host.start()
        self.addCleanup(host.stop)
        core = patch.object(bootstrap, "CoreClient")
        self.core = core.start()
        self.core.return_value.request.return_value = {"setupRequired": True}
        self.addCleanup(core.stop)

    def test_extension_keeps_credential_inode_fingerprint_and_bounded_lifetime(self):
        original = self.path.read_bytes()
        inode = self.path.stat().st_ino
        fingerprints = self.installation.state["files"].copy()
        result = bootstrap.extend_bootstrap(self.installation)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.path.stat().st_ino, inode)
        self.assertEqual(self.installation.state["files"], fingerprints)
        self.assertEqual(result["expiresAt"], int(self.path.stat().st_mtime) + 1800)
        self.assertFalse(result["credentialReplaced"])
        self.assertFalse(result["accountCreated"])

    def test_initialized_or_expected_owner_blocks_extension(self):
        before = self.path.stat().st_mtime_ns
        self.core.return_value.request.return_value = {"setupRequired": False}
        with self.assertRaisesRegex(ValueError, "E_BOOTSTRAP_ALREADY_INITIALIZED"):
            bootstrap.extend_bootstrap(self.installation)
        self.installation.state["ownerSetup"] = "authenticated"
        self.core.return_value.request.return_value = {"setupRequired": True}
        with self.assertRaisesRegex(ValueError, "E_BOOTSTRAP_EXPECTED_OWNER"):
            bootstrap.extend_bootstrap(self.installation)
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_failed_initial_intent_save_does_not_extend_window(self):
        before = self.path.stat().st_mtime_ns
        with (
            patch.object(
                self.installation,
                "save",
                side_effect=OSError("synthetic journal failure"),
            ),
            self.assertRaises(OSError),
        ):
            bootstrap.extend_bootstrap(self.installation)
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.assertNotIn("bootstrapExtension", self.installation.state)

    def test_interruption_after_touch_resumes_same_deadline_after_reload(self):
        save = self.installation.save
        count = 0

        def interrupted():
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("synthetic interruption after metadata change")
            save()

        with (
            patch.object(self.installation, "save", side_effect=interrupted),
            self.assertRaises(OSError),
        ):
            bootstrap.extend_bootstrap(self.installation)
        pending = json.loads((self.root / "install-state.json").read_text())[
            "bootstrapExtension"
        ]
        reloaded = load_installation(self.root)
        with patch.object(
            bootstrap.time, "time", return_value=pending["requestedAt"] + 30
        ):
            result = bootstrap.extend_bootstrap(reloaded)
        self.assertEqual(result["expiresAt"], pending["expiresAt"])
        self.assertEqual(int(self.path.stat().st_mtime), pending["requestedAt"])
        self.assertEqual(reloaded.state["bootstrapExtension"]["phase"], "applied")

    def test_cancelled_offer_does_not_mutate_state(self):
        before = self.path.stat().st_mtime_ns
        with (
            patch("builtins.input", return_value="CANCEL"),
            self.assertRaisesRegex(ValueError, "E_BOOTSTRAP_EXPIRED"),
        ):
            bootstrap.offer_bootstrap_extension(
                self.installation, {"bootstrapExtendReview": "Review"}
            )
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.host.assert_not_called()
