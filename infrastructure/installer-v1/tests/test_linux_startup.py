"""Startup policy/fence tests. Systemd and host probes are explicitly injected."""

import contextlib
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linux_startup as startup
from update_compose import Compose


class LinuxStartup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        raw = b"test fixture worker; never executed"
        digest = hashlib.sha256(raw).hexdigest()
        name = "maintenance-" + digest[:32]
        (self.root / name).write_bytes(raw)
        self.value = {
            "formatVersion": 1,
            "enabled": True,
            "workerFile": name,
            "workerSha256": digest,
            "unitSha256": "b" * 64,
            "state": "registered",
            "machine": "a" * 64,
            "daemon": {"id": "fixture-daemon", "sockets": ["/run/docker.sock"]},
        }
        self.installation = SimpleNamespace(
            target=self.root,
            state={
                "installationId": "02a58c66-9878-4c05-8e0b-0895f323c231",
                "files": {name: digest},
                "startupPolicy": copy.deepcopy(self.value),
            },
            verify_files=Mock(),
            start=Mock(),
            save=Mock(),
        )

    def invoke(self):
        with contextlib.ExitStack() as stack:
            for name in ("require_root", "validate_host", "validate_runtime"):
                stack.enter_context(patch.object(startup, name))
            stack.enter_context(
                patch.object(startup, "machine_binding", return_value="a" * 64)
            )
            stack.enter_context(
                patch.object(
                    startup, "installation_lock", return_value=contextlib.nullcontext()
                )
            )
            stack.enter_context(
                patch.object(
                    startup, "load_installation", return_value=self.installation
                )
            )
            return startup.background_start(self.root)

    def test_pending_update_never_starts_any_role(self):
        for phase in (
            "downloading",
            "migrating",
            "activating",
            "recovering",
            "unexpected",
        ):
            with self.subTest(phase=phase):
                self.installation.state["updateTransaction"] = {"phase": phase}
                self.assertEqual(self.invoke(), {"healthy": False, "deferred": True})
        self.installation.start.assert_not_called()
        self.installation.verify_files.assert_not_called()

    def test_retired_prepared_disabled_uninstalled_never_start(self):
        for key, value in (
            ("authority", {}),
            ("preparedForRestore", True),
            ("stage", "uninstalled"),
        ):
            with self.subTest(key=key):
                self.installation.state[key] = value
                self.assertTrue(self.invoke()["deferred"])
                del self.installation.state[key]
        self.installation.state["startupPolicy"]["enabled"] = False
        self.assertTrue(self.invoke()["deferred"])
        self.installation.start.assert_not_called()

    def test_completed_or_recovered_update_checks_real_start_before_health(self):
        for phase in ("complete", "recovered"):
            self.installation.state["updateTransaction"] = {"phase": phase}
            self.assertEqual(self.invoke(), {"healthy": True, "deferred": False})
        self.assertEqual(self.installation.start.call_count, 2)
        self.assertTrue(self.installation.state["platformStartupAttempt"]["healthy"])

    def test_changed_worker_cannot_start_even_while_update_is_fenced(self):
        (self.root / self.value["workerFile"]).write_bytes(b"changed")
        self.installation.state["updateTransaction"] = {"phase": "migrating"}
        with self.assertRaisesRegex(ValueError, "E_STARTUP_WORKER"):
            self.invoke()
        self.installation.start.assert_not_called()

    def test_cloned_host_rejected(self):
        with (
            patch.object(startup, "machine_binding", return_value="c" * 64),
            self.assertRaisesRegex(ValueError, "E_STARTUP_HOST_CHANGED"),
        ):
            startup.require_bound(self.installation)

    def test_failed_start_clears_previous_healthy_checkpoint(self):
        self.installation.state["platformStartupAttempt"] = {"healthy": True}
        self.installation.start.side_effect = ValueError("E_WEB")
        with self.assertRaisesRegex(ValueError, "E_WEB"):
            self.invoke()
        self.assertFalse(self.installation.state["platformStartupAttempt"]["healthy"])
        self.assertEqual(
            self.installation.state["platformStartupAttempt"]["state"], "failed"
        )

    def test_strict_policy_rejects_malformed_daemon_and_boolean_version(self):
        for key, value in (
            ("formatVersion", True),
            ("enabled", "yes"),
            ("daemon", {"id": 8, "sockets": []}),
        ):
            self.installation.state["startupPolicy"] = {**self.value, key: value}
            with self.assertRaisesRegex(ValueError, "E_STARTUP_POLICY"):
                startup.policy(self.installation)

    def test_supervisor_has_finite_restart_budget_and_no_stop_lock_recursion(self):
        self.installation.target = PurePosixPath("/var/lib/kyrion")
        text = startup.definition(self.installation, self.value["workerFile"])
        self.assertIn("StartLimitIntervalSec=infinity\nStartLimitBurst=3", text)
        self.assertIn("Requires=docker.service", text)
        self.assertIn("--background-platform-start", text)
        self.assertNotIn("ExecStop=", text)

    def test_maintenance_override_remains_last(self):
        self.installation.state["files"][startup.OVERLAY] = "d" * 64
        adapter = object.__new__(Compose)
        adapter.installation, adapter.root, adapter.run = (
            self.installation,
            self.root,
            Mock(),
        )
        override = self.root / "fixture-maintenance.yml"
        with patch("update_compose.path", return_value=override):
            adapter.compose("up", maintenance=True)
        args = adapter.run.call_args.args
        self.assertLess(
            args.index(str(self.root / startup.OVERLAY)), args.index(str(override))
        )
        self.assertEqual(args[-1], "up")

    def test_legacy_or_malformed_worker_capability_rejected(self):
        for raw in (
            b"{}",
            b"[]",
            b'{"formatVersion":true,"linuxComposeStart":true}',
            b'{"formatVersion":1,"linuxComposeStart":false}',
        ):
            with (
                patch.object(
                    startup.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0, stdout=raw),
                ),
                self.assertRaisesRegex(ValueError, "E_STARTUP_FROZEN_REQUIRED"),
            ):
                startup.require_capability(self.root / "fixture", self.root)

    def test_worker_probe_failure_never_becomes_capability_success(self):
        for result in (
            SimpleNamespace(returncode=2, stdout=b"{}"),
            SimpleNamespace(returncode=0, stdout=b" " * 16385),
        ):
            with (
                patch.object(startup.subprocess, "run", return_value=result),
                self.assertRaisesRegex(ValueError, "E_STARTUP_WORKER"),
            ):
                startup.require_capability(self.root / "fixture", self.root)


if __name__ == "__main__":
    unittest.main()
