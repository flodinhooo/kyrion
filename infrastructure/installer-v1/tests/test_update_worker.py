"""Real signed policy and durable check logic; scheduler/SQL are injected."""

import base64
import copy
import hashlib
import json
import os
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_update_check as fixtures
import update_worker
from runtime import Installation
from update_schedule import linux_plan, publish_unit


class WorkerTests(unittest.TestCase):
    setUp = fixtures.UpdateCheck.setUp
    check = fixtures.UpdateCheck.check

    def policy(self):
        return {
            "formatVersion": 1,
            "revision": str(uuid.uuid4()),
            "enabled": True,
            "feed": self.args.feed,
            "trust": self.trust,
            "workerFile": "maintenance-" + "a" * 32,
        }

    def prepare(self):
        self.installation.state["updatePolicy"] = self.policy()
        self.enterContext(
            patch.object(
                update_worker,
                "installation_lock",
                side_effect=lambda _: __import__("contextlib").nullcontext(),
            )
        )
        self.enterContext(
            patch.object(
                update_worker, "load_installation", return_value=self.installation
            )
        )
        self.enterContext(patch.object(update_worker, "require_worker"))
        self.enterContext(patch.object(update_worker, "validate_host"))
        self.enterContext(
            patch.object(update_worker, "read_build", return_value={"version": "1.0.0"})
        )
        self.enterContext(patch("operational_restore.require_admin"))

    def test_check_commits_real_signed_candidate_for_policy_revision(self):
        self.prepare()
        # Reuse the real signature fixture, not a mocked successful checker.
        raw = json.dumps(self.index, sort_keys=True).encode()
        envelope = json.dumps(
            {
                "keyId": "fixture",
                "payload": base64.b64encode(raw).decode(),
                "signature": base64.b64encode(self.key.sign(raw)).decode(),
            }
        ).encode()
        with patch("release_policy.fetch_document", return_value=envelope):
            self.assertEqual(update_worker.run(self.root), 0)
        self.assertTrue(self.installation.state["updateCheck"]["available"])
        self.assertIsNone(self.installation.state["updateAttempt"]["error"])
        self.assertFalse(
            self.installation.state["updateCheck"]["installedAutomatically"]
        )

    def test_network_failure_retains_last_success_without_secret_output(self):
        self.prepare()
        self.check()
        previous = copy.deepcopy(self.installation.state["updateCheck"])
        with patch(
            "release_policy.fetch_document",
            side_effect=OSError("private-token-do-not-log"),
        ):
            self.assertEqual(update_worker.run(self.root), 2)
        self.assertEqual(previous, self.installation.state["updateCheck"])
        self.assertEqual(
            self.installation.state["updateAttempt"]["error"], "E_UPDATE_CHECK"
        )
        self.assertNotIn("private-token", str(self.installation.state))

    def test_automatic_failure_records_only_safe_error_and_no_success(self):
        self.prepare()

        def failing(_target):
            raise OSError("synthetic-secret-never-export")

        self.assertEqual(update_worker.automatic_attempt(self.root, failing), 2)
        result = self.installation.state["automaticUpdateAttempt"]
        self.assertEqual(result["error"], "E_UPDATE_AUTOMATIC")
        self.assertFalse(result["completed"])
        self.assertNotIn("synthetic-secret", str(self.installation.state))

    def test_policy_revision_race_is_rejected_before_database_or_network(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "E_UPDATE_POLICY_CHANGED"):
            __import__("maintenance").check_updates(
                self.args,
                trusted_document=self.trust,
                policy_revision=str(uuid.uuid4()),
            )
        self.sql.assert_not_called()

    def test_retired_and_inactive_targets_never_check(self):
        self.prepare()
        for value in (
            {"authority": {"status": "retired"}},
            {"preparedForRestore": True},
        ):
            with self.subTest(value=value):
                previous = copy.deepcopy(self.installation.state)
                self.installation.state.update(value)
                with self.assertRaises(ValueError):
                    update_worker.run(self.root)
                self.installation.state = previous
        self.sql.assert_not_called()

    def test_policy_validation_refuses_untrusted_urls_and_commands(self):
        for field, value in (
            ("feed", "http://example.test/index"),
            ("feed", "https://user:password@example.test/index"),
            ("feed", "https://example.test/index?token=secret"),
            ("workerFile", "../../bin/sh"),
            ("formatVersion", True),
            ("revision", "not-a-uuid"),
        ):
            policy = self.policy()
            policy[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                update_worker.validate_policy(policy)

    def test_linux_units_are_fixed_finite_and_cannot_inject_systemd_expansions(self):
        units = linux_plan(
            str(uuid.uuid4()), "/var/lib/kyrion", "maintenance-" + "a" * 32
        )
        service = next(
            text for name, text in units.items() if name.endswith(".service")
        )
        timer = next(text for name, text in units.items() if name.endswith(".timer"))
        self.assertIn("Type=oneshot", service)
        self.assertIn("TimeoutStartSec=10min", service)
        self.assertIn("OnBootSec=2min", timer)
        self.assertIn("OnUnitActiveSec=24h", timer)
        self.assertNotIn("Persistent", timer)
        for target in (
            "/var/lib/%n",
            "/var/lib/kyrion\nExecStart=/bin/sh",
            "/var/lib/a b",
        ):
            with self.assertRaises(ValueError):
                linux_plan(str(uuid.uuid4()), target, "maintenance-" + "a" * 32)

    def test_configuration_resumes_after_scheduler_failure_without_replacing_worker(
        self,
    ):
        target = self.root / "installed"
        Installation(
            target,
            {"release": "1.1.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        ).save()
        worker = self.root / "synthetic-worker"
        worker.write_bytes(
            b"Synthetic frozen-worker fixture; not a runnable executable"
        )
        digest = hashlib.sha256(worker.read_bytes()).hexdigest()
        # Only the frozen executable/lifecycle boundary is injected here. File
        # publication, hashes, policy persistence and resume use the real journal.
        with (
            patch("operational_restore.require_admin"),
            patch.object(update_worker, "validate_host"),
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", str(worker)),
            patch.object(
                update_worker, "read_build", return_value={"version": "1.0.0"}
            ),
            patch(
                "update_schedule.operate", side_effect=ValueError("E_UPDATE_SYSTEMD")
            ),
            self.assertRaisesRegex(ValueError, "E_UPDATE_SYSTEMD"),
        ):
            update_worker.configure(target, self.args.feed, self.trust_file, digest)
        from recovery import load_installation

        prepared = load_installation(target)
        policy = copy.deepcopy(prepared.state["updatePolicy"])
        published = target / policy["workerFile"]
        self.assertEqual(published.read_bytes(), worker.read_bytes())
        with (
            patch("operational_restore.require_admin"),
            patch.object(update_worker, "validate_host"),
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "executable", str(worker)),
            patch.object(
                update_worker, "read_build", return_value={"version": "1.0.0"}
            ),
            patch(
                "update_schedule.operate",
                return_value={"state": "registered", "coldBootVerified": False},
            ) as scheduler,
        ):
            result = update_worker.configure(
                target, self.args.feed, self.trust_file, digest
            )
            self.assertEqual(result["state"], "registered")
            self.assertEqual(load_installation(target).state["updatePolicy"], policy)
            self.assertEqual(published.read_bytes(), worker.read_bytes())
            scheduler.assert_called_once()
        if os.name == "posix":
            self.assertEqual(published.stat().st_mode & 0o777, 0o700)

    def test_unit_publication_is_atomic_and_never_overwrites_foreign_content(self):
        name = "kyrion-" + str(uuid.uuid4()) + "-updates.service"
        with (
            patch(
                "update_schedule.os.link", side_effect=OSError("synthetic interruption")
            ),
            self.assertRaises(OSError),
        ):
            publish_unit(self.root, name, "complete intended content")
        self.assertFalse((self.root / name).exists())
        self.assertFalse(list(self.root.glob(".kyrion-unit-*")))
        publish_unit(self.root, name, "complete intended content")
        self.assertEqual((self.root / name).read_text(), "complete intended content")
        with self.assertRaises(FileExistsError):
            publish_unit(self.root, name, "replacement refused")
        self.assertEqual((self.root / name).read_text(), "complete intended content")

    def test_installed_trust_rotation_verifies_signature_and_updates_revision(self):
        self.prepare()
        previous = copy.deepcopy(self.installation.state["updatePolicy"])
        replacement = copy.deepcopy(self.trust)
        replacement["epoch"] += 1
        payload = json.dumps(
            {
                "kind": "trust-rotation",
                "expiresAt": int(time.time()) + 3600,
                "replacement": replacement,
            }
        ).encode()
        envelope = self.root / "rotation.json"
        envelope.write_text(
            json.dumps(
                {
                    "keyId": "fixture",
                    "payload": base64.b64encode(payload).decode(),
                    "signature": base64.b64encode(self.key.sign(payload)).decode(),
                }
            )
        )
        digest = hashlib.sha256(envelope.read_bytes()).hexdigest()
        result = update_worker.rotate_policy(self.root, envelope, digest)
        current = self.installation.state["updatePolicy"]
        self.assertEqual(result["trustEpoch"], 3)
        self.assertNotEqual(current["revision"], previous["revision"])
        self.assertEqual(current["workerFile"], previous["workerFile"])
        self.assertEqual(current["feed"], previous["feed"])
        self.assertFalse(result["scheduleChanged"])
        saved = copy.deepcopy(self.installation.state)
        with self.assertRaisesRegex(ValueError, "E_TRUST_ROLLBACK"):
            update_worker.rotate_policy(self.root, envelope, digest)
        self.assertEqual(saved, self.installation.state)

    def test_changed_rotation_document_never_changes_installed_policy(self):
        self.prepare()
        envelope = self.root / "rotation.json"
        envelope.write_bytes(b"changed document")
        saved = copy.deepcopy(self.installation.state)
        with self.assertRaisesRegex(ValueError, "E_UPDATE_POLICY_CHANGED"):
            update_worker.rotate_policy(self.root, envelope, "0" * 64)
        self.assertEqual(saved, self.installation.state)
