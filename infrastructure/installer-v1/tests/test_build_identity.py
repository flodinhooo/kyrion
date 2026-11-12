"""Actual embedded build identity and unreleased source safeguards."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_identity import DEVELOPMENT_VERSION, read_build
from maintenance import check_updates


class Identity(unittest.TestCase):
    def test_source_is_explicitly_unreleased_and_frozen_missing_stamp_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(read_build(root, False)["version"], DEVELOPMENT_VERSION)
            with self.assertRaisesRegex(ValueError, "E_INSTALLER_BUILD"):
                read_build(root, True)

    def test_exact_release_and_development_versions_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for version in ("2.3.4", "0.0.0-dev.20261113.1"):
                (root / "installer-build.json").write_text(
                    json.dumps({"formatVersion": 1, "version": version})
                )
                self.assertEqual(read_build(root, True)["version"], version)

    def test_malformed_duplicate_or_oversize_stamp_fails_closed(self):
        malformed = [
            "{}",
            "[]",
            '{"formatVersion":true,"version":"1.2.3"}',
            '{"formatVersion":1,"version":"latest"}',
            '{"formatVersion":1,"version":42}',
            '{"formatVersion":1,"version":"1.2.3","version":"9.9.9"}',
            "x" * 4097,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for raw in malformed:
                (root / "installer-build.json").write_text(raw)
                with self.assertRaisesRegex(ValueError, "E_INSTALLER_BUILD"):
                    read_build(root, True)

    def test_unreleased_build_cannot_fetch_update_feed_as_a_fake_stable_installer(self):
        with (
            patch("release_policy.fetch_document") as fetch,
            patch("maintenance.installation_lock") as lock,
            self.assertRaisesRegex(ValueError, "E_INSTALLER_UNRELEASED"),
        ):
            check_updates(SimpleNamespace(installer_version=DEVELOPMENT_VERSION))
        fetch.assert_not_called()
        lock.assert_not_called()
