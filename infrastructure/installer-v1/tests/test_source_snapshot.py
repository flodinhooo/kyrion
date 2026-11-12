"""Public source sealing tests; no compiler or host installation involved."""

import hashlib
import runpy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
stage_sources = runpy.run_path(str(ROOT / "release/source_snapshot.py"))[
    "stage_sources"
]


class SourceSnapshot(unittest.TestCase):
    def test_mutable_checkout_cannot_change_sealed_compiler_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "guided.py").write_bytes(b"original public source")
            hashes = stage_sources(source, root / "sealed", ("guided.py",))
            (source / "guided.py").write_bytes(b"concurrent checkout change")
            self.assertEqual(
                (root / "sealed/guided.py").read_bytes(), b"original public source"
            )
            self.assertEqual(
                hashes["guided.py"],
                hashlib.sha256(b"original public source").hexdigest(),
            )

    def test_private_or_traversing_sources_are_never_copied(self):
        for name in (".env", "../private-token.txt"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(ValueError):
                    stage_sources(root, root / "sealed", (name,))
                self.assertFalse((root / "sealed").exists())
