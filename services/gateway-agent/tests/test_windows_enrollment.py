"""Actual Windows storage; Core enrollment boundary is an explicit protocol double."""

import json
import os
import secrets
import unittest
import uuid
from unittest.mock import patch

from windows_test_support import private_root

from kyrion_gateway_agent import client, enrollment, windows_storage


@unittest.skipUnless(os.name == "nt", "Actual Windows prepared enrollment storage")
class WindowsEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(private_root())
        self.config = self.root / "agent" / "agent.json"
        self.pending = self.config.with_name("agent.json.enrollment.json")
        self.code = self.root / "code"
        windows_storage.publish(self.code, secrets.token_urlsafe(32).encode())
        self.identity = {
            "hostname": "windows-fixture",
            "osName": "Windows",
            "osVersion": "synthetic",
            "architecture": "amd64",
        }
        self.node_id = str(uuid.uuid4())
        self.requests = []

    def acknowledge(self, *arguments, **options):
        pending = json.loads(enrollment.read_private(self.pending))
        self.assertEqual(pending["node_credential"], options["node_credential"])
        self.requests.append(options)
        return client.EnrollmentResult(self.node_id, options["node_credential"])

    def begin(self):
        return enrollment.enroll_prepared(
            self.config, url="https://localhost:8443", token_file=self.code, identity=self.identity
        )

    def test_lost_core_acknowledgement_reuses_private_identity_and_original_version(self):
        def lost(*arguments, **options):
            self.acknowledge(*arguments, **options)
            raise client.CoreRequestError("E_SYNTHETIC_LOST_ACK")

        with (
            patch.object(client, "enroll", side_effect=lost),
            self.assertRaises(client.CoreRequestError),
        ):
            self.begin()
        original = json.loads(enrollment.read_private(self.pending))
        with (
            patch.object(client, "enroll", side_effect=self.acknowledge),
            patch.object(enrollment, "__version__", "synthetic-newer-runtime"),
        ):
            result = enrollment.enroll_prepared(self.config)
        self.assertEqual(result.node_id, self.node_id)
        self.assertEqual(result.gateway_token, original["node_credential"])
        self.assertEqual(self.requests[0]["agent_version"], self.requests[1]["agent_version"])
        self.assertFalse(self.pending.exists())
        self.assertNotIn(result.gateway_token, repr(result))
        windows_storage.read_private(self.config)

    def test_complete_configuration_finishes_pending_cleanup_without_another_request(self):
        publish = enrollment.publish

        def interrupted(path, raw):
            publish(path, raw)
            if path == self.config:
                raise KeyboardInterrupt()

        with (
            patch.object(client, "enroll", side_effect=self.acknowledge),
            patch.object(enrollment, "publish", interrupted),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.begin()
        self.assertTrue(self.config.exists())
        self.assertTrue(self.pending.exists())
        with patch.object(client, "enroll") as request:
            result = enrollment.enroll_prepared(self.config)
        request.assert_not_called()
        self.assertEqual(result.node_id, self.node_id)
        self.assertFalse(self.pending.exists())

    def test_existing_completed_identity_is_never_replaced_by_another_enrollment(self):
        with patch.object(client, "enroll", side_effect=self.acknowledge):
            self.begin()
        before = enrollment.read_private(self.config)
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_CONFIG_EXISTS"),
        ):
            self.begin()
        request.assert_not_called()
        self.assertEqual(enrollment.read_private(self.config), before)

    def test_runtime_lock_reuses_existing_agent_mutex_and_releases_it(self):
        with (
            enrollment.runtime_lock(self.config),
            self.assertRaisesRegex(ValueError, "E_AGENT_RUNTIME_BUSY"),
            enrollment.runtime_lock(self.config),
        ):
            self.fail("duplicate runtime acquired configuration")
        with enrollment.runtime_lock(self.config):
            pass

    def test_bound_pending_survives_lost_ack_and_refuses_space_change(self):
        space = str(uuid.uuid4())

        def lost(*arguments, **options):
            saved = json.loads(enrollment.read_private(self.pending))
            self.assertEqual(saved["formatVersion"], 2)
            self.assertEqual(saved["expected_space_id"], space)
            self.assertEqual(options["expected_space_id"], space)
            raise client.CoreRequestError("E_SYNTHETIC_LOST_ACK")

        with (
            patch.object(client, "enroll", side_effect=lost),
            self.assertRaises(client.CoreRequestError),
        ):
            enrollment.enroll_prepared(
                self.config,
                url="https://localhost:8443",
                token_file=self.code,
                identity=self.identity,
                expected_space_id=space,
            )
        before = enrollment.read_private(self.pending)
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_CONFLICT"),
        ):
            enrollment.enroll_prepared(self.config, expected_space_id=str(uuid.uuid4()))
        request.assert_not_called()
        self.assertEqual(enrollment.read_private(self.pending), before)

        def acknowledge(*arguments, **options):
            self.assertEqual(options["expected_space_id"], space)
            return client.EnrollmentResult(self.node_id, options["node_credential"], space)

        with patch.object(client, "enroll", side_effect=acknowledge):
            result = enrollment.enroll_prepared(self.config)
        self.assertEqual(result.space_id, space)
        self.assertEqual(result.gateway_token, json.loads(before)["node_credential"])
        self.assertFalse(self.pending.exists())

    def test_legacy_pending_cannot_silently_gain_new_space_expectation(self):
        with (
            patch.object(client, "enroll", side_effect=client.CoreRequestError("E_SYNTHETIC")),
            self.assertRaises(client.CoreRequestError),
        ):
            self.begin()
        before = enrollment.read_private(self.pending)
        with (
            patch.object(client, "enroll") as request,
            self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_CONFLICT"),
        ):
            enrollment.enroll_prepared(self.config, expected_space_id=str(uuid.uuid4()))
        request.assert_not_called()
        self.assertEqual(enrollment.read_private(self.pending), before)
        with patch.object(client, "enroll", side_effect=self.acknowledge):
            self.assertIsNone(enrollment.enroll_prepared(self.config).space_id)
