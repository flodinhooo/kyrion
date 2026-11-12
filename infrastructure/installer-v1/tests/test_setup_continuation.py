"""Maintenance dispatch fixtures; actual account/SQL/TLS evidence is separate."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance
import native_runtime
import onboarding


class Continuation(unittest.TestCase):
    def test_owner_recovery_uses_selected_space_without_capturing_secrets(self):
        space = str(uuid.uuid4())
        args = SimpleNamespace(
            target=Path("fixture"),
            diagnostics=None,
            owner_recovery="rotate",
            recovery_space=None,
        )
        installation = SimpleNamespace(state={"selectedSpace": {"id": space}})
        messages = {
            "maintenanceReview": "Review",
            "recoveryMaintenanceReview": "Recovery",
        }
        with (
            patch.object(
                maintenance, "installation_lock", return_value=contextlib.nullcontext()
            ),
            patch.object(maintenance, "load_installation", return_value=installation),
            patch.object(onboarding, "provision_recovery") as recovery,
            patch("builtins.input", side_effect=["MAINTAIN", "RECOVERY"]),
        ):
            self.assertEqual(maintenance.run(args, messages), 0)
        recovery.assert_called_once_with(installation, space, messages, "rotate")

    def test_owner_recovery_cancel_changes_nothing(self):
        args = SimpleNamespace(
            target=Path("fixture"), diagnostics=None, owner_recovery="complete"
        )
        with (
            patch.object(maintenance, "load_installation") as load,
            patch("builtins.input", side_effect=["MAINTAIN", "CANCEL"]),
            self.assertRaisesRegex(ValueError, "E_CONFIRMATION"),
        ):
            maintenance.run(
                args,
                {
                    "maintenanceReview": "Review",
                    "recoveryMaintenanceReview": "Recovery",
                },
            )
        load.assert_not_called()

    def test_existing_setup_can_continue_without_loading_a_release_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                target=Path(directory), diagnostics=None, continue_setup=True
            )
            installation = SimpleNamespace(
                state={
                    "backend": "windows-native",
                    "ownerSetup": "authenticated",
                    "centralIdentity": "linked",
                }
            )
            output = io.StringIO()
            with (
                patch.object(maintenance.os, "name", "nt"),
                patch.object(
                    maintenance,
                    "installation_lock",
                    return_value=contextlib.nullcontext(),
                ),
                patch.object(
                    maintenance, "load_installation", return_value=installation
                ),
                patch.object(native_runtime, "permissions") as permissions,
                patch.object(onboarding, "guided_setup") as setup,
                patch("builtins.input", return_value="MAINTAIN"),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(
                    maintenance.run(args, {"maintenanceReview": "Review"}), 0
                )
            permissions.assert_called_once_with(args.target, "verify")
            setup.assert_called_once_with(installation, {"maintenanceReview": "Review"})
            self.assertEqual(json.loads(output.getvalue())["centralIdentity"], "linked")

    def test_unowned_installation_cannot_reach_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                target=Path(directory), diagnostics=None, continue_setup=True
            )
            installation = SimpleNamespace(state={"backend": "windows-native"})
            with (
                patch.object(maintenance.os, "name", "nt"),
                patch.object(
                    maintenance,
                    "installation_lock",
                    return_value=contextlib.nullcontext(),
                ),
                patch.object(
                    maintenance, "load_installation", return_value=installation
                ),
                patch.object(
                    native_runtime,
                    "permissions",
                    side_effect=ValueError("E_NATIVE_OWNER"),
                ),
                patch.object(onboarding, "guided_setup") as setup,
                patch("builtins.input", return_value="MAINTAIN"),
                self.assertRaisesRegex(ValueError, "E_NATIVE_OWNER"),
            ):
                maintenance.run(args, {"maintenanceReview": "Review"})
            setup.assert_not_called()
