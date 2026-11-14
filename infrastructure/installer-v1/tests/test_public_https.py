"""Real SSL contexts/resources; explicit OS trust absence is injected here."""

import os
import shutil
import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import public_https as transport


class PublicHttpsTests(unittest.TestCase):
    def missing_store(self):
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.enterContext(
            patch.object(
                transport.ssl,
                "get_default_verify_paths",
                return_value=SimpleNamespace(cafile=None, capath=None),
            )
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.enterContext(
            patch.object(transport.ssl, "create_default_context", return_value=context)
        )
        return context

    def test_real_pinned_public_bundle_and_license_metadata(self):
        path, metadata = transport.bundle()
        self.assertEqual(metadata["sha256"], transport.BUNDLE_SHA256)
        self.assertEqual(metadata["version"], "2026.10.23")
        self.assertEqual(metadata["license"], "MPL-2.0")
        self.assertNotIn(b"PRIVATE KEY", path.read_bytes())

    def test_missing_os_store_loads_actual_pinned_bundle_with_verification(self):
        bare = self.missing_store()
        self.assertEqual(bare.cert_store_stats()["x509_ca"], 0)
        context, source, loaded = transport.configured_context()
        self.assertIs(context, bare)
        self.assertEqual(source, "bundled")
        self.assertEqual(loaded, 0)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_explicit_trust_override_is_preserved_even_when_empty(self):
        self.missing_store()
        with (
            patch.dict(os.environ, {"SSL_CERT_FILE": "explicit-empty-test-store"}),
            patch.object(transport, "bundle") as fallback,
        ):
            context, source, loaded = transport.configured_context()
        self.assertEqual((source, loaded), ("explicit", 0))
        fallback.assert_not_called()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_existing_default_file_does_not_trigger_trust_substitution(self):
        self.missing_store()
        with (
            patch.object(
                transport.ssl,
                "get_default_verify_paths",
                return_value=SimpleNamespace(
                    cafile="existing-empty-policy.pem", capath=None
                ),
            ),
            patch.object(transport, "bundle") as fallback,
        ):
            _context, source, _loaded = transport.configured_context()
        self.assertEqual(source, "system")
        fallback.assert_not_called()

    def test_hashed_system_directory_keeps_lazy_os_trust_policy(self):
        self.missing_store()
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "01234567.0").write_bytes(
                b"Synthetic store entry; never parsed as a certificate"
            )
            with (
                patch.object(
                    transport.ssl,
                    "get_default_verify_paths",
                    return_value=SimpleNamespace(cafile=None, capath=directory),
                ),
                patch.object(transport, "bundle") as fallback,
            ):
                _context, source, _loaded = transport.configured_context()
            self.assertEqual(source, "system")
            fallback.assert_not_called()

    def test_corrupted_bundle_is_refused_before_fallback_can_load_it(self):
        self.missing_store()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(transport.ROOT / "metadata.json", root / "metadata.json")
            (root / "cacert.pem").write_bytes(b"modified public data")
            with (
                patch.object(transport, "ROOT", root),
                self.assertRaisesRegex(ValueError, "E_PUBLIC_CA_BUNDLE"),
            ):
                transport.context()

    def test_os_store_error_never_retries_through_a_weaker_context(self):
        with (
            patch.object(
                transport.ssl,
                "create_default_context",
                side_effect=ssl.SSLError("synthetic invalid store"),
            ),
            patch.object(transport, "bundle") as fallback,
            self.assertRaisesRegex(ValueError, "E_PUBLIC_CA_STORE"),
        ):
            transport.context()
        fallback.assert_not_called()

    def test_status_is_resource_and_policy_evidence_not_a_network_test(self):
        result = transport.status()
        self.assertTrue(result["bundleVerified"])
        self.assertFalse(result["connectionTested"])
        self.assertTrue(result["certificateVerificationRequired"])
        self.assertTrue(result["hostnameVerificationRequired"])
