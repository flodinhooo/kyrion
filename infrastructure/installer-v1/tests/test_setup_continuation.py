"""Maintenance dispatch fixtures; actual account/SQL/TLS evidence is separate."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance
import native_runtime
import onboarding


class Continuation(unittest.TestCase):
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
