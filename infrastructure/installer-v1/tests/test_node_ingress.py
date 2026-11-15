"""Ingress intent/fencing with actual private files and explicit runtime doubles."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import node_ingress
from authority import require_active
from recovery import load_installation
from runtime import Installation
from update_compose import Compose


class IngressPolicyTests(unittest.TestCase):
    def test_enabled_worker_without_integrity_checked_executable_is_refused(self):
        for policy in (True, {}, {"enabled": 1}, {"enabled": True}):
            installation = Mock(state={"backupPolicy": policy})
            with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_WORKER"):
                node_ingress.require_workers(installation)

    def test_pending_proxy_fence_preserves_update_and_retirement_fences(self):
        state = {"agentIngressTransition": {"phase": "published"}}
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_PENDING"):
            require_active(state)
        require_active(state, ingress=True)
        with self.assertRaisesRegex(ValueError, "E_AUTHORITY_INACTIVE"):
            require_active({**state, "authority": {"phase": "retired"}}, ingress=True)
        for phase in ("verified", "recovered"):
            require_active({"agentIngressTransition": {"phase": phase}})

    def test_authority_is_read_from_core_not_from_role_names_or_browser_fields(self):
        client = Mock()
        client.request.return_value = {
            "enabled": True,
            "roles": ["OWNER"],
            "permissions": [],
        }
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_PERMISSION"):
            node_ingress.actor(client)
        self.assertEqual(client.request.call_count, 1)

    def test_proxy_validation_payload_uses_bounded_stdin_and_not_command_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            adapter = Compose.__new__(Compose)
            adapter.docker = Path(temporary) / "synthetic-docker"
            adapter.root, adapter.env = Path(temporary), {}
            with patch(
                "update_compose.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, b"", b""),
            ) as run:
                adapter.run("synthetic", payload=b"synthetic public configuration")
            self.assertEqual(
                run.call_args.kwargs["input"], b"synthetic public configuration"
            )
            self.assertNotIn("stdin", run.call_args.kwargs)
            with (
                patch("update_compose.subprocess.run") as run,
                self.assertRaisesRegex(ValueError, "E_UPDATE_DOCKER_INPUT"),
            ):
                adapter.run("synthetic", payload=b"x" * 65537)
            run.assert_not_called()


@unittest.skipUnless(
    sys.platform.startswith("linux") and os.geteuid() == 0,
    "Owned Linux root filesystem fixture",
)
class IngressFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.installation = Installation(
            Path(temporary.name) / "installed",
            {"release": "0.0.0-dev.ingress-fixture", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        _, known = node_ingress.definitions(self.installation)
        self.legacy = next(value for value in known if "@kyrion_agent" not in value)
        self.installation.write(node_ingress.FILE, self.legacy)
        self.approval = {"actorId": str(uuid.uuid4()), "spaceId": str(uuid.uuid4())}
        self.runtime = Mock(spec=node_ingress.ComposeRuntime)

    def reload(self):
        return load_installation(self.installation.target, verify=False)

    def test_intent_is_durable_before_first_service_change_and_never_contains_a_session(
        self,
    ):
        def stop():
            state = json.loads(self.installation.path.read_bytes())
            value = state[node_ingress.KEY]
            self.assertEqual(state["formatVersion"], 2)
            self.assertEqual(value["phase"], "prepared")
            self.assertEqual(value["actorId"], self.approval["actorId"])
            self.assertNotIn("sessionToken", json.dumps(value))

        self.runtime.stop.side_effect = stop
        result = node_ingress.apply(
            self.installation, self.approval, "configure", runtime=self.runtime
        )
        self.assertTrue(result["agentConnectionVerified"])
        self.assertEqual(self.installation.state["formatVersion"], 1)
        require_active(self.installation.state)
        self.runtime.validate.assert_called_once()
        self.runtime.probe.assert_called_once()

    def test_interrupted_start_resumes_same_transaction_and_fences_ordinary_operations(
        self,
    ):
        self.runtime.start.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=self.runtime
            )
        identifier = self.installation.state[node_ingress.KEY]["id"]
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_PENDING"):
            load_installation(self.installation.target)
        restored = self.reload()
        self.runtime.start.side_effect = None
        second_actor = {**self.approval, "actorId": str(uuid.uuid4())}
        node_ingress.apply(restored, second_actor, "resume", runtime=self.runtime)
        value = restored.state[node_ingress.KEY]
        self.assertEqual(value["id"], identifier)
        self.assertEqual(value["actorId"], self.approval["actorId"])
        self.assertEqual(value["lastActorId"], second_actor["actorId"])
        self.assertEqual(
            load_installation(restored.target).state[node_ingress.KEY]["phase"],
            "verified",
        )

    def test_replace_before_journal_acknowledgement_is_reconciled_without_unknown_bytes(
        self,
    ):
        original = node_ingress.checkpoint

        def checkpoint(installation, phase):
            if phase == "published":
                raise KeyboardInterrupt
            original(installation, phase)

        with (
            patch.object(node_ingress, "checkpoint", side_effect=checkpoint),
            self.assertRaises(KeyboardInterrupt),
        ):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=self.runtime
            )
        restored = self.reload()
        self.assertEqual(restored.state[node_ingress.KEY]["phase"], "stopped")
        result = node_ingress.apply(
            restored, self.approval, "resume", runtime=self.runtime
        )
        self.assertTrue(result["agentConnectionVerified"])

    def test_explicit_recovery_restores_only_original_proxy_without_core_login(self):
        self.runtime.probe.side_effect = RuntimeError("E_SYNTHETIC_CORE_LOSS")
        with self.assertRaises(RuntimeError):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=self.runtime
            )
        restored = self.reload()
        result = node_ingress.apply(restored, None, "recover", runtime=self.runtime)
        self.assertTrue(result["originalProxyTlsVerified"])
        self.assertFalse(result["agentConnectionVerified"])
        self.assertEqual((restored.target / node_ingress.FILE).read_text(), self.legacy)
        self.assertEqual(restored.state[node_ingress.KEY]["recoveredBy"], "os-root")
        require_active(restored.state)

    def test_missing_recorded_proxy_can_recover_after_interrupted_publication(self):
        self.runtime.start.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=self.runtime
            )
        (self.installation.target / node_ingress.FILE).unlink()
        self.runtime.start.side_effect = None
        result = node_ingress.apply(
            self.reload(), None, "recover", runtime=self.runtime
        )
        self.assertTrue(result["originalProxyTlsVerified"])
        self.assertEqual(
            (self.installation.target / node_ingress.FILE).read_text(), self.legacy
        )

    def test_custom_and_changed_configurations_never_reach_the_runtime(self):
        path = self.installation.target / node_ingress.FILE
        path.write_bytes(b"synthetic custom configuration")
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_CUSTOM"):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=self.runtime
            )
        self.assertEqual(self.runtime.mock_calls, [])
        self.assertEqual(path.read_bytes(), b"synthetic custom configuration")

    def test_foreign_space_cannot_resume_an_existing_approval(self):
        self.runtime.start.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=self.runtime
            )
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_PERMISSION"):
            node_ingress.apply(
                self.reload(),
                {**self.approval, "spaceId": str(uuid.uuid4())},
                "resume",
                runtime=self.runtime,
            )

    def test_old_enabled_worker_is_refused_and_disabled_worker_is_not_executed(self):
        name = "maintenance-" + "a" * 32
        self.installation.write(name, b"synthetic worker, never executed")
        self.installation.state["startupPolicy"] = {"enabled": True, "workerFile": name}
        with patch.object(
            node_ingress.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                [], 0, b'{"formatVersion":1}', b""
            ),
        ) as run:
            with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_WORKER"):
                node_ingress.require_workers(self.installation)
            run.assert_called_once()
        self.installation.state["startupPolicy"]["enabled"] = False
        with patch.object(node_ingress.subprocess, "run") as run:
            node_ingress.require_workers(self.installation)
            run.assert_not_called()

    def test_fifo_configuration_is_refused_without_waiting_for_a_writer(self):
        path = self.installation.target / node_ingress.FILE
        path.unlink()
        os.mkfifo(path, 0o600)
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_OWNERSHIP"):
            node_ingress.inspect(self.installation)
