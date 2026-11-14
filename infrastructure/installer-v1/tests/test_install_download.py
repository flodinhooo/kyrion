"""Actual loopback TLS/Ed25519/archive tests; privilege/OS ACLs are injected."""

import json
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle
import install_download as download
import native_bundle
import native_staging
import test_update_download as fixtures
from recovery import load_installation


class FreshDownloadTests(unittest.TestCase):
    def setUp(self):
        self.http = fixtures.DownloadTests(
            "test_review_rejection_never_fetches_large_artifact"
        )
        self.http.setUp()
        self.addCleanup(self.http.doCleanups)
        installed, self.selected = self.http.staged_fixture(schema=download.SCHEMA)
        policy = load_installation(installed).state["updatePolicy"]
        self.enterContext(
            patch.object(
                download,
                "embedded",
                return_value={
                    "feed": policy["feed"],
                    "trust": policy["trust"],
                },
            )
        )
        self.enterContext(
            patch.object(download, "read_build", return_value={"version": "1.0.0"})
        )
        self.enterContext(patch.object(download.backup_store, "secure_directory"))
        self.enterContext(
            patch.object(
                download.backup_store,
                "create_directory",
                side_effect=lambda p: p.mkdir(mode=0o700),
            )
        )
        self.enterContext(
            patch.object(
                download.backup_store,
                "private_output",
                side_effect=lambda p, _: os.fdopen(
                    os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
                ),
            )
        )
        self.target = self.http.root / "fresh-target"
        self.space = self.enterContext(
            patch.object(
                download.shutil,
                "disk_usage",
                return_value=SimpleNamespace(free=100 * 1024**3),
            )
        )

    def prepare(self, review=lambda _: True):
        return download.prepare(self.target, "windows/amd64", review=review)

    def test_review_rejection_downloads_no_payload_and_creates_no_cache(self):
        with self.assertRaisesRegex(ValueError, "E_INSTALL_DOWNLOAD_CANCELLED"):
            self.prepare(lambda _: False)
        self.assertFalse(self.target.exists())
        self.assertFalse(
            (
                self.target.parent / ("." + self.target.name + ".release-download")
            ).exists()
        )
        self.assertNotIn(
            "/kyrion-windows-amd64.zip", [p for p, _ in self.http.requests]
        )

    def test_insufficient_space_refuses_payload_before_cache_creation(self):
        self.space.return_value = SimpleNamespace(free=11 * 1024**3)
        with self.assertRaisesRegex(ValueError, "E_DOWNLOAD_DISK"):
            self.prepare()
        self.assertNotIn(
            "/kyrion-windows-amd64.zip", [p for p, _ in self.http.requests]
        )

    def test_interrupted_metadata_publication_retries_without_adopting_partial_cache(
        self,
    ):
        publish = download.backup_store.publish
        with (
            patch.object(
                download.backup_store,
                "publish",
                side_effect=OSError("synthetic publication cut"),
            ),
            self.assertRaises(OSError),
        ):
            self.prepare()
        root = self.target.parent / ("." + self.target.name + ".release-download")
        self.assertFalse(root.exists())
        self.assertTrue(list(root.parent.glob(root.name + ".preparing-*")))
        with patch.object(download.backup_store, "publish", side_effect=publish):
            cached, authority = self.prepare()
        self.assertEqual(cached, root)
        native_bundle.authenticated_review(root, authority)

    def test_signed_download_private_native_staging_and_unpack_without_downloaded_key(
        self,
    ):
        root, authority = self.prepare()
        checked = native_bundle.authenticated_review(root, authority)
        self.assertEqual(checked.manifest_sha256, self.selected["manifestSha256"])
        self.assertFalse(self.target.exists())
        from runtime import Installation

        installation = Installation(
            self.target,
            checked.manifest,
            checked.manifest_sha256,
            "fixture.test",
            "127.0.0.1",
        )
        with patch.object(
            native_staging.shutil,
            "disk_usage",
            return_value=type("Space", (), {"free": 100 * 1024**3})(),
        ):
            staged = native_staging.stage_bundle(installation, root, authority, checked)
        output = self.target / "payload"
        native_bundle.unpack(staged, authority, output)
        self.assertTrue(output.is_dir())
        self.assertFalse((staged / "public.pem").exists())
        self.assertFalse((staged / "manifest.sig").exists())
        self.assertTrue((staged / download.PROOF).is_file())

    def test_interrupted_download_resumes_exact_cache_with_https_range(self):
        self.http.mode = "interrupt"
        with self.assertRaisesRegex(ValueError, "E_DOWNLOAD_INTERRUPTED"):
            self.prepare()
        self.http.mode = "normal"
        root, authority = self.prepare()
        self.assertTrue(any(ranged for _, ranged in self.http.requests))
        native_bundle.authenticated_review(root, authority)
        requests = len(self.http.requests)
        self.prepare()
        self.assertEqual(len(self.http.requests), requests)

    def test_cached_proof_expiry_and_tampering_are_refused(self):
        root, authority = self.prepare()
        with (
            patch("release_policy.time.time", return_value=time.time() + 7200),
            self.assertRaisesRegex(ValueError, "EXPIRED"),
        ):
            bundle.verify_signature(root, authority)
        proof = json.loads((root / download.PROOF).read_bytes())
        proof["signature"] = "A" * 88
        (root / download.PROOF).write_text(json.dumps(proof))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_changed_manifest_unknown_cache_file_and_unconfigured_build_fail_closed(
        self,
    ):
        root, authority = self.prepare()
        raw = (root / "manifest.json").read_bytes()
        (root / "manifest.json").write_bytes(raw + b" ")
        with self.assertRaisesRegex(ValueError, "E_INSTALL_DOWNLOAD_PROOF"):
            bundle.verify_signature(root, authority)
        (root / "manifest.json").write_bytes(raw)
        (root / "unknown.file").write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "E_INSTALL_DOWNLOAD_OWNER"):
            self.prepare()
        with (
            patch.object(download, "embedded", return_value=None),
            self.assertRaisesRegex(ValueError, "E_INSTALLER_CHANNEL_REQUIRED"),
        ):
            self.prepare()
