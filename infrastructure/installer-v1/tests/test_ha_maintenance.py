"""HA maintenance orchestration only; provider/SQL acceptance is separate."""

import contextlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance


class Maintenance(unittest.TestCase):
    def run_command(self, action, replies, response=None):
        installation = SimpleNamespace(state={"backend": "windows-native"}, save=Mock())
        args = SimpleNamespace(
            target=Path("fixture"), diagnostics=None, home_assistant=action
        )
        client = Mock()
        client.request.side_effect = response
        with (
            patch(
                "maintenance.installation_lock", return_value=contextlib.nullcontext()
            ),
            patch("maintenance.load_installation", return_value=installation),
            patch("native_runtime.permissions"),
            patch("onboarding.CoreClient", return_value=client),
            patch("linked_onboarding.linked_setup") as auth,
            patch("onboarding.guided_home_assistant") as configure,
            patch("builtins.input", side_effect=replies),
            patch("builtins.print"),
        ):
            try:
                result = maintenance.run(
                    args,
                    {"maintenanceReview": "Review", "haDisconnectReview": "Disconnect"},
                )
                return result, installation, client, auth, configure
            except ValueError:
                client.close.assert_called_once()
                self.assertNotIn("homeAssistant", installation.state)
                raise

    def test_configure_uses_same_linked_identity_and_closes_session(self):
        result, _installation, client, auth, configure = self.run_command(
            "configure", ["MAINTAIN"]
        )
        self.assertEqual(result, 0)
        auth.assert_called_once()
        configure.assert_called_once()
        client.close.assert_called_once()

    def test_disconnect_requires_confirmation_and_core_state_evidence(self):
        _, installation, client, _, configure = self.run_command(
            "disconnect",
            ["MAINTAIN", "DISCONNECT"],
            [{"disconnected": True}, {"configured": False}],
        )
        self.assertEqual(installation.state["homeAssistant"], "disconnected")
        self.assertEqual(
            client.request.call_args_list[0].args,
            ("DELETE", "/v1/integrations/home-assistant"),
        )
        configure.assert_not_called()
        client.close.assert_called_once()

    def test_cancel_does_not_remove_configuration(self):
        with self.assertRaisesRegex(ValueError, "E_CONFIRMATION"):
            self.run_command("disconnect", ["MAINTAIN", "CANCEL"])

    def test_saved_state_alone_is_not_disconnect_success(self):
        with self.assertRaisesRegex(ValueError, "E_HA_DISCONNECT"):
            self.run_command(
                "disconnect",
                ["MAINTAIN", "DISCONNECT"],
                [{"disconnected": True}, {"configured": True}],
            )
