"""Recovery orchestration fixtures; no services or actual recovery codes."""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_recovery


class Recovery(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.space = str(uuid.uuid4())
        self.key = self.root / "recovery" / (self.space + ".host-key")
        self.installation = SimpleNamespace(
            target=self.root, state={}, verify_files=MagicMock(), save=MagicMock()
        )
        self.manager = MagicMock(spec=native_recovery.ServiceManager)
        self.manager.__enter__.return_value = self.manager
        self.manager.opened.return_value.__enter__.return_value = object()
        replacements = {
            "read_configuration": {
                "hostname": "fixture.test",
                "address": "127.0.0.1",
                "ports": {},
            },
            "preflight": None,
            "permissions": None,
            "role_plan": (self.root / "java.exe", [], {"FIXTURE": "private"}),
            "plan_for": {"name": "fixture"},
            "ServiceManager": self.manager,
        }
        for name, value in replacements.items():
            patcher = patch.object(native_recovery, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.platform = patch.object(native_recovery.os, "name", "nt")

    def test_core_tool_inherits_console_and_restarts_without_capturing_code(self):
        def complete(*_args, **_kwargs):
            self.key.write_bytes(b"a" * 43)
            return SimpleNamespace(returncode=0)

        with (
            self.platform,
            patch.object(
                native_recovery.subprocess, "run", side_effect=complete
            ) as command,
            patch.object(native_recovery, "start_services") as restart,
        ):
            native_recovery.provision_owner_recovery(self.installation, self.space)
        arguments, options = command.call_args
        self.assertIn(
            "org.springframework.boot.loader.launch.PropertiesLauncher", arguments[0]
        )
        self.assertIn(
            "-Dloader.main=dev.kyrion.core.security.LocalSecurityAdmin", arguments[0]
        )
        self.assertEqual(arguments[0][-3:], ["provision", self.space, str(self.key)])
        self.assertFalse(
            set(options)
            & {"input", "stdout", "stderr", "capture_output", "stdin", "creationflags"}
        )
        self.assertEqual(self.manager.stop.call_count, 3)
        restart.assert_called_once_with(self.installation)
        self.assertEqual(
            self.installation.state, {"recovery": "provisioned-by-core-host-tool"}
        )

    def test_tool_failure_restores_services_without_claiming_recovery(self):
        with (
            self.platform,
            patch.object(
                native_recovery.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=1),
            ),
            patch.object(native_recovery, "start_services") as restart,
            self.assertRaisesRegex(ValueError, "E_RECOVERY_NOT_PROVISIONED"),
        ):
            native_recovery.provision_owner_recovery(self.installation, self.space)
        restart.assert_called_once()
        self.assertEqual(self.installation.state, {})

    def test_existing_key_is_preserved_before_service_mutation(self):
        self.key.parent.mkdir()
        self.key.write_bytes(b"operator-owned-existing-key")
        with (
            self.platform,
            patch.object(native_recovery.subprocess, "run") as command,
            self.assertRaisesRegex(ValueError, "E_RECOVERY_EXISTING"),
        ):
            native_recovery.provision_owner_recovery(self.installation, self.space)
        command.assert_not_called()
        self.manager.stop.assert_not_called()
        self.assertEqual(self.key.read_bytes(), b"operator-owned-existing-key")

    def test_foreign_service_refused_before_any_stop(self):
        self.manager.assert_owned.side_effect = ValueError("E_SERVICE_FOREIGN")
        with (
            self.platform,
            patch.object(native_recovery.subprocess, "run") as command,
            patch.object(native_recovery, "start_services") as restart,
            self.assertRaisesRegex(ValueError, "E_SERVICE_FOREIGN"),
        ):
            native_recovery.provision_owner_recovery(self.installation, self.space)
        self.manager.stop.assert_not_called()
        command.assert_not_called()
        restart.assert_not_called()
