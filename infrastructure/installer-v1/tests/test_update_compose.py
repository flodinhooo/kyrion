"""Real image-archive rewriting; Docker execution is explicitly injected."""

import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from update_compose import Compose


class ComposeUpdateImages(unittest.TestCase):
    def test_untagged_loading_preserves_layers_and_foreign_tag_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "source.tar"
            manifest = [
                {
                    "Config": "config.json",
                    "RepoTags": ["shared/image:current"],
                    "Layers": ["layer.tar"],
                }
            ]
            with tarfile.open(archive, "w") as package:
                for name, raw in {
                    "manifest.json": json.dumps(manifest).encode(),
                    "config.json": b"{}",
                    "layer.tar": b"synthetic layer bytes",
                }.items():
                    entry = tarfile.TarInfo(name)
                    entry.size = len(raw)
                    package.addfile(entry, io.BytesIO(raw))
            before = archive.read_bytes()
            adapter = object.__new__(Compose)
            adapter.root = root
            adapter.installation = SimpleNamespace(
                configuration={"architecture": "linux/amd64"}
            )
            calls = []

            def run(*args, **_options):
                calls.append(args)
                if args[0] == "load":
                    with tarfile.open(args[2]) as rewritten:
                        loaded = json.load(rewritten.extractfile("manifest.json"))
                        self.assertEqual(loaded[0]["RepoTags"], [])
                        self.assertEqual(
                            rewritten.extractfile("layer.tar").read(),
                            b"synthetic layer bytes",
                        )
                    return b"loaded synthetic image"
                return json.dumps(
                    [
                        {
                            "Id": "sha256:" + "a" * 64,
                            "Os": "linux",
                            "Architecture": "amd64",
                        }
                    ]
                ).encode()

            adapter.run = run
            adapter.load_untagged(archive, "sha256:" + "a" * 64)
            self.assertEqual(archive.read_bytes(), before)
            self.assertEqual([call[0] for call in calls], ["load", "image"])
            self.assertEqual(list(root.iterdir()), [archive])

    def test_loaded_wrong_architecture_fails_even_after_successful_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "source.tar"
            with tarfile.open(archive, "w") as package:
                raw = b'[{"Config":"config.json","RepoTags":["synthetic/image:1"],"Layers":[]}]'
                entry = tarfile.TarInfo("manifest.json")
                entry.size = len(raw)
                package.addfile(entry, io.BytesIO(raw))
            adapter = object.__new__(Compose)
            adapter.root = root
            adapter.installation = SimpleNamespace(
                configuration={"architecture": "linux/amd64"}
            )
            adapter.run = lambda *args, **_options: (
                b"loaded"
                if args[0] == "load"
                else json.dumps(
                    [
                        {
                            "Id": "sha256:" + "a" * 64,
                            "Os": "linux",
                            "Architecture": "arm64",
                        }
                    ]
                ).encode()
            )
            with self.assertRaisesRegex(ValueError, "E_IMAGE"):
                adapter.load_untagged(archive, "sha256:" + "a" * 64)
