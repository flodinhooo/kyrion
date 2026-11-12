"""Native download staging with real signed synthetic ZIP bytes, no processes."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_native_bundle as fixture
from native_bundle import authenticated_review
from native_staging import stage_bundle
from runtime import Installation


class Staging(unittest.TestCase):
    # Reuse the synthetic signing fixture without inheriting/re-running its tests.
    setUp = fixture.NativeBundleTests.setUp
    bundle = fixture.NativeBundleTests.bundle
    signed_bundle = fixture.NativeBundleTests.signed_bundle
    write_manifest = fixture.NativeBundleTests.write_manifest

    def test_private_archive_survives_source_changes_and_repeats(self):
        if importlib.util.find_spec("cryptography") is None:
            self.skipTest("Installer runtime dependency")
        _, key = self.signed_bundle()
        review = authenticated_review(self.root, key)
        installation = Installation(
            self.root / "installation",
            review.manifest,
            review.manifest_sha256,
            "fixture.test",
            "127.0.0.1",
        )
        private = stage_bundle(installation, self.root, key, review)
        expected = (private / "kyrion-windows-amd64.zip").read_bytes()
        (self.root / "kyrion-windows-amd64.zip").write_bytes(b"changed original source")
        repeated = stage_bundle(installation, self.root, key, review)
        self.assertEqual(private, repeated)
        self.assertEqual((private / "kyrion-windows-amd64.zip").read_bytes(), expected)

    def test_interrupted_private_copy_is_preserved_and_replaced_without_adoption(self):
        if importlib.util.find_spec("cryptography") is None:
            self.skipTest("Installer runtime dependency")
        _, key = self.signed_bundle()
        review = authenticated_review(self.root, key)
        installation = Installation(
            self.root / "installation",
            review.manifest,
            review.manifest_sha256,
            "fixture.test",
            "127.0.0.1",
        )

        def interrupted(_source, target, _expected):
            target.write_bytes(b"partial public archive")
            raise OSError("synthetic interruption")

        with (
            patch("native_staging.copy_image_input", side_effect=interrupted),
            self.assertRaises(OSError),
        ):
            stage_bundle(installation, self.root, key, review)
        private = stage_bundle(installation, self.root, key, review)
        partials = list(private.glob(".native-archive-*"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].read_bytes(), b"partial public archive")
        self.assertEqual(
            (private / "kyrion-windows-amd64.zip").read_bytes(),
            (self.root / "kyrion-windows-amd64.zip").read_bytes(),
        )
