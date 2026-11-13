"""Build-bound public trust, tamper refusal and local setup scheduling intent."""

import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_channel
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from runtime import Installation


class EmbeddedChannel(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage = self.root / "staged-public-build"
        self.stage.mkdir()
        now = int(time.time())
        self.channel = {
            "formatVersion": 1,
            "feed": "https://updates.example.test/index.json",
            "trust": {
                "formatVersion": 1,
                "epoch": 1,
                "keys": [
                    {
                        "id": "fixture",
                        "pem": Ed25519PrivateKey.generate()
                        .public_key()
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
            },
        }
        self.input = self.root / "public-channel.json"
        self.input.write_text(json.dumps(self.channel), encoding="utf-8")

    def test_stable_build_requires_channel_and_development_does_not_invent_one(self):
        with self.assertRaisesRegex(ValueError, "E_INSTALLER_CHANNEL_REQUIRED"):
            release_channel.stamp(self.stage, "1.2.3", None)
        self.assertEqual(list(self.stage.iterdir()), [])
        release_channel.stamp(self.stage, "0.0.0-dev.1", None)
        self.assertEqual(
            release_channel.summary(self.stage, True),
            {"configured": False, "feed": None, "trustEpoch": None, "sha256": None},
        )

    def test_configured_public_bytes_are_bound_to_build_and_tamper_is_rejected(self):
        identity = release_channel.stamp(self.stage, "1.2.3", self.input)
        self.assertEqual(release_channel.embedded(self.stage, True), self.channel)
        result = release_channel.summary(self.stage, True)
        self.assertTrue(result["configured"])
        self.assertEqual(result["sha256"], identity["releaseChannelSha256"])
        with (self.stage / release_channel.RESOURCE).open("ab") as output:
            output.write(b"\n")
        with self.assertRaisesRegex(ValueError, "E_INSTALLER_CHANNEL_CHANGED"):
            release_channel.embedded(self.stage, True)

    def test_unbound_side_loaded_trust_is_not_adopted(self):
        release_channel.stamp(self.stage, "0.0.0-dev.1", None)
        (self.stage / release_channel.RESOURCE).write_bytes(self.input.read_bytes())
        with self.assertRaisesRegex(ValueError, "E_INSTALLER_CHANNEL_UNBOUND"):
            release_channel.embedded(self.stage, True)

    def test_credentials_queries_unknown_fields_and_missing_rotation_authority_fail(
        self,
    ):
        for feed in (
            "http://updates.example.test/index",
            "https://user:password@updates.example.test/index",
            "https://updates.example.test/index?token=secret",
            "https://updates.example.test/index\n",
        ):
            value = copy.deepcopy(self.channel)
            value["feed"] = feed
            with self.subTest(feed=feed), self.assertRaises(ValueError):
                release_channel.validate(value)
        value = copy.deepcopy(self.channel)
        value["trust"]["keys"][0]["usages"] = ["release-index"]
        with self.assertRaises(ValueError):
            release_channel.validate(value)
        value = {**self.channel, "privateKey": "never accepted"}
        with self.assertRaises(ValueError):
            release_channel.validate(value)

    def test_skipping_schedule_does_not_contact_channel_or_change_installation(self):
        installation = Installation(
            self.root / "installed",
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        before = (installation.target / "install-state.json").read_bytes()
        messages = {
            key: key
            for key in (
                "updatesChannelOffer",
                "updatesChannelExisting",
                "updatesChannelConfigured",
            )
        }
        with (
            patch.object(release_channel, "embedded", return_value=self.channel),
            patch("builtins.input", return_value="skip"),
            patch("builtins.print"),
            patch("update_worker.configure") as configure,
        ):
            release_channel.offer(installation.target, messages)
        configure.assert_not_called()
        self.assertEqual(
            (installation.target / "install-state.json").read_bytes(), before
        )

    def test_registration_failure_is_saved_without_success_or_secret_output(self):
        installation = Installation(
            self.root / "installed",
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        keys = (
            "updatesChannelOffer",
            "updatesChannelExisting",
            "updatesChannelConfigured",
            "updatesChannelFailed",
        )
        messages = {key: key for key in keys}
        with (
            patch.object(release_channel, "embedded", return_value=self.channel),
            patch("builtins.input", return_value="ENABLE-CHECKS"),
            patch("builtins.print") as output,
            patch(
                "update_worker.configure",
                side_effect=OSError("synthetic-secret-do-not-export"),
            ),
        ):
            release_channel.offer(installation.target, messages)
        from recovery import load_installation

        state = load_installation(installation.target).state
        self.assertEqual(state["updates"], "schedule-not-configured")
        self.assertEqual(state["updateSetupError"], "E_UPDATE_CONFIG")
        self.assertNotIn("synthetic-secret", str(state))
        self.assertNotIn("updatesChannelConfigured", str(output.call_args_list))

    def test_existing_rotated_or_disabled_policy_is_preserved_without_prompt(self):
        installation = Installation(
            self.root / "installed",
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        installation.state["updatePolicy"] = {
            "enabled": False,
            "feed": self.channel["feed"],
            "trust": self.channel["trust"],
        }
        installation.save()
        with (
            patch.object(release_channel, "embedded", return_value=self.channel),
            patch("builtins.input") as prompt,
            patch("builtins.print"),
            patch("update_worker.configure") as configure,
        ):
            release_channel.offer(
                installation.target, {"updatesChannelExisting": "existing"}
            )
        configure.assert_not_called()
        prompt.assert_not_called()
