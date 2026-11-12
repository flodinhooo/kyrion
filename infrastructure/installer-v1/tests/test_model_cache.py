"""Real Ed25519 catalogs and persisted journals; network fetch is isolated."""

import base64
import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from model_cache import cached_catalog, refresh_catalog
from models import guided_recommendation, load_catalog
from recovery import load_installation
from runtime import Installation


class CatalogCache(unittest.TestCase):
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
        self.key = Ed25519PrivateKey.generate()
        now = int(time.time())
        self.trust = {
            "formatVersion": 1,
            "epoch": 1,
            "keys": [
                {
                    "id": "fixture",
                    "pem": self.key.public_key()
                    .public_bytes(
                        serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    .decode(),
                    "notBefore": now - 60,
                    "notAfter": now + 86400,
                    "usages": ["model-catalog", "trust-rotation"],
                }
            ],
        }
        self.document = load_catalog()

    def envelope(self, sequence=2, change=False):
        document = copy.deepcopy(self.document)
        document["sequence"] = sequence
        if change:
            document["models"][0]["downloadBytes"] += 1
        raw = json.dumps(document, sort_keys=True).encode()
        return json.dumps(
            {
                "keyId": "fixture",
                "payload": base64.b64encode(raw).decode(),
                "signature": base64.b64encode(self.key.sign(raw)).decode(),
            }
        ).encode()

    def refresh(self, raw):
        with patch("model_cache.fetch_document", return_value=raw):
            return refresh_catalog(
                self.installation, "https://catalog.example.test/models", self.trust
            )

    def test_restart_keeps_verified_catalog_and_rejects_rollback_or_equivocation(self):
        result = self.refresh(self.envelope())
        self.assertTrue(result["signatureVerified"])
        reloaded = load_installation(self.root)
        self.assertEqual(cached_catalog(reloaded)["sequence"], 2)
        before = (self.root / "install-state.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "E_MODEL_CATALOG_SEQUENCE"):
            self.refresh(self.envelope(1))
        with self.assertRaisesRegex(ValueError, "E_MODEL_CATALOG_EQUIVOCATION"):
            self.refresh(self.envelope(2, True))
        self.assertEqual((self.root / "install-state.json").read_bytes(), before)
        self.assertEqual(self.refresh(self.envelope())["sequence"], 2)
        self.assertEqual(self.refresh(self.envelope(3))["sequence"], 3)

    def test_tamper_and_wrong_key_do_not_replace_cache(self):
        self.refresh(self.envelope())
        before = copy.deepcopy(self.installation.state)
        envelope = json.loads(self.envelope(3))
        envelope["signature"] = base64.b64encode(b"x" * 64).decode()
        with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
            self.refresh(json.dumps(envelope).encode())
        self.assertEqual(before, self.installation.state)

    def test_failed_atomic_save_does_not_advance_memory_or_disk(self):
        self.refresh(self.envelope())
        before = copy.deepcopy(self.installation.state)
        disk = (self.root / "install-state.json").read_bytes()
        with (
            patch.object(
                self.installation,
                "save",
                side_effect=OSError("synthetic journal failure"),
            ),
            self.assertRaises(OSError),
        ):
            self.refresh(self.envelope(3))
        self.assertEqual(before, self.installation.state)
        self.assertEqual(disk, (self.root / "install-state.json").read_bytes())

    def test_skip_never_opens_an_expired_or_unavailable_catalog(self):
        def unavailable():
            raise ValueError("must not load on skip")

        with patch("builtins.input", return_value="skip"):
            self.assertIsNone(
                guided_recommendation({}, {"aiPlanNow": "AI"}, unavailable)
            )

    def test_changed_cached_bytes_are_rejected_offline(self):
        self.refresh(self.envelope())
        self.installation.state["modelCatalog"]["envelope"] = base64.b64encode(
            b"tampered"
        ).decode()
        with self.assertRaisesRegex(ValueError, "E_MODEL_CACHE"):
            cached_catalog(self.installation)

    def test_trust_epoch_cannot_be_lowered_after_restart(self):
        self.trust["epoch"] = 2
        self.refresh(self.envelope())
        self.trust["epoch"] = 1
        with self.assertRaisesRegex(ValueError, "E_MODEL_TRUST_ROLLBACK"):
            self.refresh(self.envelope(3))

    def test_refresh_does_not_require_an_unexpired_bundled_catalog(self):
        def signed_only(envelope=None, *args, **kwargs):
            if envelope is None:
                raise ValueError("synthetic expired bundled document")
            return load_catalog(envelope, *args, **kwargs)

        with patch("model_cache.load_catalog", side_effect=signed_only):
            self.assertEqual(self.refresh(self.envelope())["sequence"], 2)

    def test_expired_cache_is_not_replaced_by_older_builtin_data(self):
        self.refresh(self.envelope())
        expired = self.document["expiresAt"] + 1
        with (
            patch("release_policy.time.time", return_value=expired),
            self.assertRaises(ValueError),
        ):
            cached_catalog(load_installation(self.root))
        self.assertEqual(self.installation.state["modelCatalog"]["sequence"], 2)
