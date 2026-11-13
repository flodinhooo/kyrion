"""Synthetic build-input policy tests; actual vendor/runtime evidence is separate."""

import hashlib
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "release")]
import gpg_profile

producer = runpy.run_path(str(ROOT / "release/prepare-windows-gpg.py"))


class GpgProfile(unittest.TestCase):
    def verify(self, root):
        with patch.object(
            gpg_profile, "__file__", str(root.parent / (root.name + "-fixture.py"))
        ):
            return gpg_profile.verify_profile(root)

    def test_archive_selection_rejects_traversal_aliases_and_links(self):
        review = producer["review_listing"]
        review(
            b"Path = /build/vendor.exe\n----------\nPath = $PLUGINSDIR//home/upstream/build.ini\nPath = bin/gpg.exe\nPath = share/help.txt\n"
        )
        for body in (
            "Path = bin/../outside",
            "Path = bin\\..\\outside",
            "Path = bin/gpg.exe\nPath = BIN/GPG.EXE",
            "Path = bin/gpg.exe\nSymbolic Link = /outside",
            "Path = bin/gpg.exe\nHard Link = /outside",
            "Path = bin/C:/outside",
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                review(("----------\n" + body + "\n").encode())

    def test_changed_vendor_source_is_refused_before_any_tool_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            (root / "vendor.exe").write_bytes(b"changed")
            lock = {
                "sources": {
                    "archive": {"file": "vendor.exe", "bytes": 7, "sha256": "a" * 64}
                }
            }
            with self.assertRaisesRegex(ValueError, "E_GPG_VENDOR_INTEGRITY"):
                producer["source_files"](root, lock)

    def fixture(self, root):
        lock = json.loads((ROOT / "release/gnupg-windows-lock.json").read_text())
        records = {}
        for name in (
            "bin/gpg.exe",
            "bin/gpgconf.exe",
            "bin/gpg-agent.exe",
            "bin/gpgconf.ctl",
            "README.txt",
        ):
            path = root / name
            path.parent.mkdir(exist_ok=True, parents=True)
            raw = (
                b""
                if name.endswith(".ctl")
                else b"synthetic public build input; never executed"
            )
            path.write_bytes(raw)
            records[name] = {
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        for kind in ("sourceArchive", "sourceSignature", "keys"):
            source = lock["sources"][kind]
            path = root / "share/kyrion-source" / source["file"]
            path.parent.mkdir(exist_ok=True, parents=True)
            raw = ("synthetic corresponding source " + kind).encode()
            path.write_bytes(raw)
            source["bytes"] = len(raw)
            source["sha256"] = hashlib.sha256(raw).hexdigest()
            records[path.relative_to(root).as_posix()] = {
                "bytes": len(raw),
                "sha256": source["sha256"],
            }
        notice = root / "share/kyrion-source/licenses/COPYING"
        notice.parent.mkdir(exist_ok=True, parents=True)
        notice.write_bytes(b"synthetic license fixture")
        records[notice.relative_to(root).as_posix()] = {
            "bytes": notice.stat().st_size,
            "sha256": hashlib.sha256(notice.read_bytes()).hexdigest(),
        }
        (root.parent / "gnupg-windows-lock.json").write_text(json.dumps(lock))
        metadata = {
            "formatVersion": 1,
            "kind": "kyrion-portable-gnupg",
            "version": lock["version"],
            "sourceSha256": lock["sources"]["archive"]["sha256"],
            "sourceUrl": lock["sources"]["archive"]["url"],
            "verifiedPrimaryFingerprint": lock["primaryFingerprint"],
            "vendorSignatureVerified": True,
            "correspondingSourceSignatureVerified": True,
            "files": records,
        }
        (root / "vendor.json").write_text(json.dumps(metadata))
        return metadata

    def test_profile_refuses_changed_binary_or_extra_keyring(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            metadata = self.fixture(root)
            self.assertEqual(self.verify(root), metadata)
            (root / "bin/gpg.exe").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "E_GPG_PROFILE_CHANGED"):
                self.verify(root)
            self.fixture(root)
            (root / "home").mkdir()
            (root / "home/private.key").write_bytes(b"synthetic forbidden keyring")
            with self.assertRaises(ValueError):
                self.verify(root)

    def test_profile_rejects_another_source_identity_and_missing_portable_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "profile"
            root.mkdir()
            metadata = self.fixture(root)
            metadata["verifiedPrimaryFingerprint"] = "A" * 40
            (root / "vendor.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "E_GPG_PROFILE"):
                self.verify(root)
            self.fixture(root)
            (root / "bin/gpgconf.ctl").unlink()
            with self.assertRaisesRegex(ValueError, "E_GPG_PROFILE_CHANGED"):
                self.verify(root)
