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
    def test_existing_agent_component_is_sealed_from_its_canonical_public_sources(self):
        from package import GATEWAY_FILES, source_file

        with tempfile.TemporaryDirectory() as directory:
            sealed = Path(directory) / "sealed"
            hashes = stage_sources(ROOT, sealed, GATEWAY_FILES)
            self.assertEqual(set(hashes), set(GATEWAY_FILES))
            for name in GATEWAY_FILES:
                component_root = ROOT.parents[1] / "services/gateway-agent/src"
                canonical = (
                    component_root / name if component_root.is_dir() else ROOT / name
                )
                self.assertEqual(source_file(ROOT, name), canonical)
                self.assertEqual((sealed / name).read_bytes(), canonical.read_bytes())
            self.assertEqual(
                {path.relative_to(sealed).as_posix() for path in sealed.rglob("*.py")},
                set(GATEWAY_FILES),
            )

    def test_temporary_or_unknown_sources_cannot_reach_sibling_agent_files(self):
        from package import source_file

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                source_file(root, "kyrion_gateway_agent/config.py"),
                root / "kyrion_gateway_agent/config.py",
            )
            self.assertEqual(
                source_file(ROOT, "kyrion_gateway_agent/not_reviewed.py"),
                ROOT / "kyrion_gateway_agent/not_reviewed.py",
            )
            for name in (
                "../secrets",
                "kyrion_gateway_agent/.env",
                "C:/private",
                "/private",
            ):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    source_file(root, name)

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
