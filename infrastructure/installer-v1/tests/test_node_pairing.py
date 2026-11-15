"""Pairing transfer validation and explicit fake Core/OS boundary tests."""

import datetime
import hashlib
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import node_pairing
from crypto_support import certificate, private_tls_key


class NodePairingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        raw = certificate("fixture.test", "127.0.0.1", private_tls_key())
        self.value = {
            "formatVersion": 1,
            "kind": node_pairing.KIND,
            "coreUrl": "https://fixture.test",
            "certificate": raw.decode("ascii"),
            "certificateSha256": hashlib.sha256(raw).hexdigest(),
            "enrollmentId": str(uuid.uuid4()),
            "expiresAt": (
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=9)
            )
            .isoformat()
            .replace("+00:00", "Z"),
            "enrollmentToken": "a" * 43,
            "spaceId": str(uuid.uuid4()),
            "installationId": str(uuid.uuid4()),
        }

    def test_metadata_and_repr_never_expose_the_enrollment_secret(self):
        pairing = node_pairing.validate(self.value)
        self.assertNotIn(self.value["enrollmentToken"], repr(pairing))
        self.assertNotIn("enrollmentToken", pairing.metadata())
        self.assertNotIn("certificate", pairing.metadata())
        self.assertEqual(self.value, pairing.document())

    def test_unknown_version_fields_types_and_certificate_changes_refused(self):
        for changed in (
            {"formatVersion": True},
            {"formatVersion": 2},
            {"extra": "unknown"},
            {"certificateSha256": "0" * 64},
            {"enrollmentToken": "x"},
            {"coreUrl": "http://fixture.test"},
            {"spaceId": "not-an-id"},
        ):
            with (
                self.subTest(changed=changed),
                self.assertRaises((ValueError, RuntimeError)),
            ):
                node_pairing.validate({**self.value, **changed})

    def test_expired_and_unreasonably_future_codes_are_not_renewed(self):
        for seconds in (-1, 800):
            changed = {
                **self.value,
                "expiresAt": (
                    datetime.datetime.now(datetime.UTC)
                    + datetime.timedelta(seconds=seconds)
                )
                .isoformat()
                .replace("+00:00", "Z"),
            }
            with self.assertRaisesRegex(ValueError, "E_NODE_PAIRING_EXPIRED"):
                node_pairing.validate(changed)

    def test_private_material_is_ephemeral_and_uses_reviewed_memory(self):
        pairing = node_pairing.validate(self.value)
        args = SimpleNamespace(node_pairing=self.root / "source.json")
        with node_pairing.materialize(args, pairing) as prepared:
            token = prepared.node_token_file
            self.assertEqual(token.read_text(), self.value["enrollmentToken"])
            self.assertEqual(prepared.node_ca_sha256, self.value["certificateSha256"])
            if os.name == "posix":
                self.assertEqual(token.stat().st_mode & 0o777, 0o600)
        self.assertFalse(token.exists())
        self.assertEqual(args.node_pairing, self.root / "source.json")

    @unittest.skipUnless(os.name == "posix", "POSIX private transfer storage")
    def test_public_hardlinked_and_duplicate_json_transfers_refused(self):
        path = self.root / "pairing.json"
        path.write_text(json.dumps(self.value), encoding="utf-8")
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "E_NODE_PAIRING_PRIVATE"):
            node_pairing.load(path)
        path.chmod(0o600)
        os.link(path, self.root / "other")
        with self.assertRaisesRegex(ValueError, "E_NODE_PAIRING_PRIVATE"):
            node_pairing.load(path)
        (self.root / "other").unlink()
        path.write_text('{"formatVersion":1,"formatVersion":1}', encoding="utf-8")
        with self.assertRaises(ValueError):
            node_pairing.load(path)

    def client(self):
        target = self.root / "installed"
        (target / "data/tls").mkdir(parents=True)
        (target / "data/tls/cert.pem").write_bytes(
            self.value["certificate"].encode("ascii")
        )
        installation = SimpleNamespace(
            target=target,
            configuration={"hostname": "fixture.test"},
            state={"installationId": self.value["installationId"]},
            verify_files=Mock(),
        )
        client = Mock()
        client.installation = installation
        client.request.side_effect = [
            {"id": self.value["spaceId"], "status": "ACTIVE"},
            {
                "id": self.value["enrollmentId"],
                "enrollmentToken": self.value["enrollmentToken"],
                "expiresAt": self.value["expiresAt"],
            },
        ]
        return client

    def test_failed_actual_ingress_probe_never_issues_a_code(self):
        node_pairing.component(require_linux=False)
        client = self.client()
        with (
            patch(
                "kyrion_gateway_agent.client.prepared_capabilities",
                side_effect=RuntimeError("synthetic ingress failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            node_pairing.export(client, "Synthetic prepared node")
        client.request.assert_not_called()
        self.assertFalse(list(client.installation.target.glob("pairing-transfer-*")))

    def test_missing_ingress_is_actionable_and_never_silently_reconfigured(self):
        node_pairing.component(require_linux=False)
        from kyrion_gateway_agent.client import CoreRequestError

        client = self.client()
        with (
            patch(
                "kyrion_gateway_agent.client.prepared_capabilities",
                side_effect=CoreRequestError("synthetic HTTP 404", 404),
            ),
            self.assertRaisesRegex(ValueError, "E_NODE_PAIRING_INGRESS"),
        ):
            node_pairing.export(client, "Synthetic prepared node")
        client.request.assert_not_called()
        self.assertFalse(list(client.installation.target.glob("pairing-transfer-*")))

    def test_export_is_exclusive_and_reuses_existing_space_and_enrollment_api(self):
        node_pairing.component(require_linux=False)
        client = self.client()
        with (
            patch("kyrion_gateway_agent.client.prepared_capabilities") as probe,
            patch.object(
                node_pairing,
                "private_directory",
                side_effect=lambda path: path.mkdir(mode=0o700),
            ),
            patch(
                "windows_security.open_secured_file",
                side_effect=lambda path, _: os.open(
                    path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                ),
            ),
        ):
            path, pairing = node_pairing.export(client, "Synthetic node")
        probe.assert_called_once()
        client.request.assert_any_call(
            "POST", "/v1/gateways/enrollments", {"displayName": "Synthetic node"}
        )
        self.assertEqual(json.loads(path.read_bytes()), self.value)
        self.assertEqual(pairing.space_id, self.value["spaceId"])
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_cancelled_export_has_no_core_or_filesystem_action(self):
        client = Mock()
        with patch("builtins.input", side_effect=["Synthetic node", "CANCEL"]):
            node_pairing.guided_export(
                client,
                {
                    "nodePairingExportScope": "Scope",
                    "devicesName": "Name",
                    "nodePairingExportReview": "Review",
                },
            )
        client.request.assert_not_called()
