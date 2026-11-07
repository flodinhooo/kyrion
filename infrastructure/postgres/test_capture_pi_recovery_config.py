"""Synthetic configuration only; never opens the actual platform directory."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "capture_config", Path(__file__).with_name("capture-pi-recovery-config.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(os.name == "posix", "POSIX file protection is required")
class CaptureConfigTest(unittest.TestCase):
    def fixture(self, root):
        platform = root / "platform"
        (platform / "tls").mkdir(parents=True)
        for name in [
            "compose.yml",
            "platform.env",
            "Caddyfile",
            "tls/server.crt",
            "tls/server.key",
        ]:
            (platform / name).write_bytes(("synthetic-" + name).encode())
        return platform

    def test_additive_capture_preserves_sources_and_restricts_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            platform = self.fixture(root)
            before = {p: p.read_bytes() for p in MODULE.sources(platform)}
            a = MODULE.capture(platform, root / "recovery")
            b = MODULE.capture(platform, root / "recovery")
            self.assertNotEqual(a, b)
            self.assertFalse((a / "INCOMPLETE").exists())
            self.assertEqual(
                len(json.loads((a / "manifest.json").read_text())["files"]), 5
            )
            for path, data in before.items():
                self.assertEqual(path.read_bytes(), data)
                saved = a / "files" / path.relative_to(platform)
                self.assertEqual(saved.read_bytes(), data)
                self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertEqual(a.stat().st_mode & 0o777, 0o700)

    def test_redirected_tls_source_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            platform = self.fixture(root)
            source = platform / "tls/server.key"
            source.unlink()
            source.symlink_to(root / "unrelated")
            with self.assertRaises(ValueError):
                MODULE.capture(platform, root / "recovery")
            self.assertFalse((root / "recovery").exists())

    def test_concurrent_source_change_leaves_only_incomplete_addition(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            platform = self.fixture(root)
            original = MODULE.read_file
            calls = 0

            def change_on_recheck(path):
                nonlocal calls
                calls += 1
                if calls == 6:
                    path.write_bytes(b"synthetic-concurrent-edit")
                return original(path)

            with (
                patch.object(MODULE, "read_file", side_effect=change_on_recheck),
                self.assertRaises(ValueError),
            ):
                MODULE.capture(platform, root / "recovery")
            additions = list((root / "recovery").iterdir())
            self.assertEqual(len(additions), 1)
            self.assertTrue((additions[0] / "INCOMPLETE").exists())
            self.assertFalse((additions[0] / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
