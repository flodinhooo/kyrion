import base64
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_policy as policy


def entry(version="1.2.0"):
    return {
        "version": version,
        "platform": "linux/arm64",
        "minimumInstaller": "1.0.0",
        "fromSchemas": [46],
        "targetSchema": 47,
        "apiMin": 1,
        "apiMax": 2,
        "manifestUrl": "https://releases.example.test/manifest.json",
        "manifestSha256": "a" * 64,
        "notesUrl": "https://releases.example.test/notes",
        "schemaDowngradeSupported": False,
        "components": {
            "core": version,
            "web": version,
            "postgres": "17.6",
            "caddy": "2.10.2",
        },
    }


class CompatibilityTests(unittest.TestCase):
    def index(self):
        return {
            "formatVersion": 1,
            "kind": "release-index",
            "sequence": 2,
            "releases": [entry(), entry("1.3.0")],
        }

    def test_latest_compatible_published_version(self):
        selected = policy.compatible_release(
            self.index(), "1.0.0", "1.1.0", "linux/arm64", 46, 1
        )
        self.assertEqual(selected["version"], "1.3.0")

    def test_schema_platform_installer_and_api_are_enforced(self):
        for installer, platform, schema, api in (
                ("0.9.0", "linux/arm64", 46, 1),
                ("1.0.0", "windows/amd64", 46, 1),
                ("1.0.0", "linux/arm64", 45, 1),
                ("1.0.0", "linux/arm64", 46, 3),
        ):
            with self.subTest(
                installer=installer, platform=platform, schema=schema, api=api
            ):
                self.assertIsNone(
                    policy.compatible_release(
                        self.index(), installer, "1.1.0", platform, schema, api
                    )
                )

    def test_channel_rollback_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "E_RELEASE_INDEX"):
            policy.compatible_release(
                self.index(), "1.0.0", "1.1.0", "linux/arm64", 46, 1, last_sequence=3
            )

    def test_no_unproven_schema_downgrade_promise(self):
        index = self.index()
        index["releases"][0]["schemaDowngradeSupported"] = True
        with self.assertRaisesRegex(ValueError, "E_RELEASE_CONTRACT"):
            policy.compatible_release(index, "1.0.0", "1.1.0", "linux/arm64", 46, 1)

    def test_unsafe_url_or_duplicate_release_is_rejected(self):
        for mode in ("url", "duplicate"):
            index = self.index()
            if mode == "url":
                index["releases"][0]["manifestUrl"] = "http://example.test/manifest"
            else:
                index["releases"].append(copy.deepcopy(index["releases"][0]))
            with self.assertRaises(ValueError):
                policy.compatible_release(index, "1.0.0", "1.1.0", "linux/arm64", 46, 1)


@unittest.skipUnless(
    shutil.which("openssl"), "OpenSSL required for actual signed-document checks"
)
class SignatureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ED25519",
                "-out",
                str(self.root / "private.pem"),
            ],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(self.root / "private.pem"),
                "-pubout",
                "-out",
                str(self.root / "public.pem"),
            ],
            capture_output=True,
            check=True,
        )
        self.trust = {
            "formatVersion": 1,
            "epoch": 1,
            "keys": [
                {
                    "id": "test-2026",
                    "pem": (self.root / "public.pem").read_text(),
                    "notBefore": 100,
                    "notAfter": 2000,
                    "usages": ["release-index", "trust-rotation"],
                }
            ],
        }

    def sign(self, document):
        payload = json.dumps(document).encode()
        (self.root / "payload").write_bytes(payload)
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-rawin",
                "-inkey",
                str(self.root / "private.pem"),
                "-in",
                str(self.root / "payload"),
                "-out",
                str(self.root / "signature"),
            ],
            capture_output=True,
            check=True,
        )
        return json.dumps(
            {
                "keyId": "test-2026",
                "payload": base64.b64encode(payload).decode(),
                "signature": base64.b64encode(
                    (self.root / "signature").read_bytes()
                ).decode(),
            }
        ).encode()

    def test_real_signature_scoped_usage_and_expiry(self):
        envelope = self.sign({"kind": "release-index", "expiresAt": 1500})
        self.assertEqual(
            policy.verify(envelope, self.trust, "release-index", now=1000)["kind"],
            "release-index",
        )
        with self.assertRaisesRegex(ValueError, "E_TRUST_KEY"):
            policy.verify(envelope, self.trust, "model-catalog", now=1000)
        with self.assertRaisesRegex(ValueError, "E_SIGNED_DOCUMENT_EXPIRED_OR_USAGE"):
            policy.verify(envelope, self.trust, "release-index", now=1600)

    def test_tampered_payload_is_rejected(self):
        envelope = json.loads(self.sign({"kind": "release-index", "expiresAt": 1500}))
        envelope["payload"] = base64.b64encode(
            b'{"kind":"release-index","expiresAt":1900}'
        ).decode()
        with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
            policy.verify(
                json.dumps(envelope).encode(), self.trust, "release-index", now=1000
            )

    def test_rotation_advances_epoch_and_cannot_replay(self):
        path = self.root / "trust.json"
        path.write_text(json.dumps(self.trust))
        next_trust = copy.deepcopy(self.trust)
        next_trust["epoch"] = 2
        envelope = self.sign(
            {"kind": "trust-rotation", "expiresAt": 1500, "replacement": next_trust}
        )
        self.assertEqual(policy.rotate(path, envelope, now=1000)["epoch"], 2)
        with self.assertRaisesRegex(ValueError, "E_TRUST_ROLLBACK"):
            policy.rotate(path, envelope, now=1000)


if __name__ == "__main__":
    unittest.main()
