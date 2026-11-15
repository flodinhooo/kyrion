"""Protected POSIX lifecycle with the HTTP boundary injected, no OS service claims."""

import hashlib
import json
import secrets
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from kyrion_gateway_agent import client, enrollment


@unittest.skipUnless(
    sys.platform.startswith("linux"), "Prepared agent storage currently supports Linux"
)
class PreparedEnrollment(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "private" / "agent.json"
        self.pending = self.config.with_name("agent.json.enrollment.json")
        self.token = self.root / "code"
        self.token.write_text(secrets.token_urlsafe(32), encoding="ascii")
        self.token.chmod(0o600)
        self.identity = {
            "hostname": "fixture",
            "osName": "Debian",
            "osVersion": "13",
            "architecture": "amd64",
        }
        self.node = str(uuid.uuid4())

    def begin(self):
        return enrollment.enroll_prepared(
            self.config, url="https://localhost:8443", token_file=self.token, identity=self.identity
        )

    def test_changed_certificate_cannot_replace_the_reviewed_fingerprint_before_pairing(self):
        certificate = self.root / "source-ca.pem"
        reviewed = hashlib.sha256(b"reviewed certificate bytes").hexdigest()
        certificate.write_bytes(b"replacement certificate bytes")
        with (
            patch.object(client, "enroll") as request,
            patch.object(client, "trusted_context") as trust,
            self.assertRaisesRegex(ValueError, "E_AGENT_TLS_CONFIGURATION"),
        ):
            enrollment.enroll_prepared(
                self.config,
                url="https://localhost:8443",
                token_file=self.token,
                certificate=certificate,
                expected_ca_sha256=reviewed,
                identity=self.identity,
            )
        request.assert_not_called()
        trust.assert_not_called()
        self.assertFalse(self.pending.exists())
        self.assertFalse(self.config.with_name("agent.json.ca.pem").exists())

    def acknowledged(self, *_arguments, **options):
        saved = json.loads(enrollment.read_private(self.pending))
        self.assertTrue(
            secrets.compare_digest(saved["node_credential"], options["node_credential"])
        )
        self.assertEqual(self.pending.stat().st_mode & 0o777, 0o600)
        return client.EnrollmentResult(self.node, options["node_credential"])

    def test_secret_is_durable_before_the_first_request_and_final_config_is_private(self):
        with patch.object(client, "enroll", side_effect=self.acknowledged):
            config = self.begin()
        self.assertEqual(config.node_id, self.node)
        self.assertTrue(config.local_only)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.pending.exists())
        self.assertNotIn(config.gateway_token, repr(config))

    def test_lost_acknowledgement_resumes_with_same_secret_and_original_identity_version(self):
        captured = []

        def interrupted(*_arguments, **options):
            captured.append(options.copy())
            self.acknowledged(**options)
            raise client.CoreRequestError("E_SYNTHETIC_LOST_RESPONSE")

        with (
            patch.object(client, "enroll", side_effect=interrupted),
            self.assertRaises(client.CoreRequestError),
        ):
            self.begin()
        self.assertFalse(self.config.exists())
        before = self.pending.read_bytes()
        with (
            patch.object(client, "enroll", side_effect=self.acknowledged) as request,
            patch.object(enrollment, "__version__", "99.0.0"),
        ):
            config = enrollment.enroll_prepared(self.config)
        self.assertTrue(
            secrets.compare_digest(config.gateway_token, captured[0]["node_credential"])
        )
        self.assertEqual(
            request.call_args.kwargs["agent_version"], json.loads(before)["agent_version"]
        )

    def test_committed_config_with_pending_cleanup_resumes_without_network(self):
        actual_unlink = Path.unlink

        def interrupted(path, *arguments, **options):
            if path == self.pending:
                raise OSError("Synthetic interruption after durable final config")
            return actual_unlink(path, *arguments, **options)

        with (
            patch.object(client, "enroll", side_effect=self.acknowledged),
            patch.object(Path, "unlink", interrupted),
            self.assertRaises(OSError),
        ):
            self.begin()
        self.assertTrue(self.config.exists() and self.pending.exists())
        with patch.object(client, "enroll") as request:
            config = enrollment.enroll_prepared(self.config)
        request.assert_not_called()
        self.assertEqual(config.node_id, self.node)
        self.assertFalse(self.pending.exists())

    def test_existing_config_is_never_overwritten_or_reenrolled(self):
        with patch.object(client, "enroll", side_effect=self.acknowledged):
            self.begin()
        original = self.config.read_bytes()
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_CONFIG_EXISTS"),
        ):
            self.begin()
        request.assert_not_called()
        self.assertEqual(self.config.read_bytes(), original)

    def prepare_interrupted(self):
        with (
            patch.object(client, "enroll", side_effect=client.CoreRequestError("offline")),
            self.assertRaises(client.CoreRequestError),
        ):
            self.begin()

    def test_core_or_code_changes_cannot_retarget_an_incomplete_claim(self):
        self.prepare_interrupted()
        original = self.pending.read_bytes()
        self.token.write_text(secrets.token_urlsafe(32), encoding="ascii")
        with patch.object(client, "enroll") as request:
            with self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_CONFLICT"):
                enrollment.enroll_prepared(self.config, url="https://other.local")
            with self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_CONFLICT"):
                enrollment.enroll_prepared(self.config, token_file=self.token)
        request.assert_not_called()
        self.assertEqual(self.pending.read_bytes(), original)

    def test_concurrent_enrollment_refuses_before_any_network_request(self):
        enrollment.private_directory(self.config.parent)
        lock = self.config.with_name("agent.json.enrollment.lock")
        with (
            enrollment.enrollment_lock(lock),
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_BUSY"),
        ):
            self.begin()
        request.assert_not_called()

    def test_public_pending_file_or_unexpected_secret_field_is_rejected(self):
        self.prepare_interrupted()
        self.pending.chmod(0o644)
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_FILE"),
        ):
            enrollment.enroll_prepared(self.config)
        request.assert_not_called()
        self.pending.chmod(0o600)
        value = json.loads(self.pending.read_bytes())
        value["web_password"] = "Synthetic forbidden field"
        self.pending.write_text(json.dumps(value), encoding="utf-8")
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_JOURNAL"),
        ):
            enrollment.enroll_prepared(self.config)
        request.assert_not_called()

    def test_symlink_token_or_config_never_reaches_the_network(self):
        link = self.root / "code-link"
        link.symlink_to(self.token)
        with patch.object(client, "enroll") as request, self.assertRaises((OSError, ValueError)):
            enrollment.enroll_prepared(
                self.config, url="https://localhost:8443", token_file=link, identity=self.identity
            )
        request.assert_not_called()
        self.assertTrue(self.token.is_file())

    def test_unsafe_parent_permissions_are_preserved_and_refused(self):
        self.config.parent.mkdir(mode=0o755)
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_PATH"),
        ):
            self.begin()
        request.assert_not_called()
        self.assertEqual(self.config.parent.stat().st_mode & 0o777, 0o755)

    def test_prepared_mode_never_uses_plain_http(self):
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_TLS_REQUIRED"),
        ):
            enrollment.enroll_prepared(
                self.config,
                url="http://localhost:8080",
                token_file=self.token,
                identity=self.identity,
            )
        request.assert_not_called()
        self.assertFalse(self.pending.exists())
