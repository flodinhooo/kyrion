"""Actual signed update policy; native SQL/SCM and network are injected."""

import base64
import contextlib
import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_release_policy import entry


class UpdateCheck(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.key = Ed25519PrivateKey.generate()
        now = int(time.time())
        self.trust = {
            "formatVersion": 1,
            "epoch": 2,
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
                    "usages": ["release-index", "trust-rotation"],
                }
            ],
        }
        self.trust_file = self.root / "trust.json"
        self.trust_file.write_text(json.dumps(self.trust))
        release = entry()
        release.update(platform="windows/amd64", fromSchemas=[49], targetSchema=50)
        self.index = {
            "formatVersion": 1,
            "kind": "release-index",
            "sequence": 5,
            "expiresAt": now + 3600,
            "releases": [release],
        }
        self.installation = SimpleNamespace(
            state={"backend": "windows-native"},
            configuration={"architecture": "windows/amd64", "release": "1.1.0"},
            save=MagicMock(),
            compose=MagicMock(),
        )
        self.args = SimpleNamespace(
            target=self.root,
            installer_version="1.0.0",
            feed="https://releases.example.test/index.json",
            trust_store=self.trust_file,
            installed_schema=None,
            installed_api=1,
        )
        self.enterContext(
            patch.object(
                maintenance,
                "installation_lock",
                side_effect=lambda _: contextlib.nullcontext(),
            )
        )
        self.enterContext(
            patch.object(
                maintenance, "load_installation", return_value=self.installation
            )
        )
        self.sql = self.enterContext(
            patch("native_runtime.installed_schema", return_value="49")
        )

    def check(self, document=None, tamper=False):
        raw = json.dumps(document or self.index, sort_keys=True).encode()
        signature = self.key.sign(raw)
        if tamper:
            signature = b"x" * 64
        envelope = json.dumps(
            {
                "keyId": "fixture",
                "payload": base64.b64encode(raw).decode(),
                "signature": base64.b64encode(signature).decode(),
            }
        ).encode()
        with patch("release_policy.fetch_document", return_value=envelope):
            return maintenance.check_updates(self.args)

    def test_native_check_uses_real_observed_schema_and_signed_compatible_candidate(
        self,
    ):
        result = self.check()
        self.assertEqual(result["candidate"]["version"], "1.2.0")
        self.assertFalse(result["installedAutomatically"])
        self.assertEqual(result["trustEpoch"], 2)
        self.installation.compose.assert_not_called()
        self.sql.assert_called_once_with(self.installation)

    def test_signature_failure_does_not_replace_last_result(self):
        self.check()
        before = copy.deepcopy(self.installation.state)
        with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
            self.check(tamper=True)
        self.assertEqual(before, self.installation.state)

    def test_rollback_and_same_sequence_changed_content_are_refused(self):
        self.check()
        for sequence, error in (
            (4, "E_RELEASE_INDEX"),
            (5, "E_UPDATE_INDEX_EQUIVOCATION"),
        ):
            changed = copy.deepcopy(self.index)
            changed["sequence"] = sequence
            changed["releases"][0]["notesUrl"] += "/changed"
            with (
                self.subTest(sequence=sequence),
                self.assertRaisesRegex(ValueError, error),
            ):
                self.check(changed)

    def test_trust_epoch_rollback_is_refused(self):
        self.check()
        self.trust["epoch"] = 1
        self.trust_file.write_text(json.dumps(self.trust))
        with self.assertRaisesRegex(ValueError, "E_UPDATE_TRUST_ROLLBACK"):
            self.check()

    def test_incompatible_schema_is_not_an_available_update(self):
        changed = copy.deepcopy(self.index)
        changed["releases"][0]["fromSchemas"] = [48]
        self.assertFalse(self.check(changed)["available"])
        self.args.installed_schema = 48
        with self.assertRaisesRegex(ValueError, "E_UPDATE_SCHEMA"):
            self.check()
