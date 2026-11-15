"""Synthetic Core responses; real RBAC and database behavior are tested in Core."""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from device_management import guided_devices, managed_devices, offer_device_setup
from onboarding import CoreClient

NODE = {
    "id": "4454e2ad-8e2e-46d2-b935-bd84165a92a0",
    "revision": "63095b1a-8d6d-4b72-b7a0-efc2b26d0e70",
    "displayName": "Fixture",
    "expectedAvailability": "unknown",
    "revokedAt": None,
}


class DeviceManagementTests(unittest.TestCase):
    def offer(self, choice, permissions=("gateways:read",)):
        self.client.installation.state = {}
        with patch("builtins.input", return_value=choice), patch("builtins.print"):
            offer_device_setup(
                self.client, self.messages, {"permissions": list(permissions)}
            )
        return self.client.installation.state["deviceSetup"]

    def test_single_device_path_preserves_existing_device_authority(self):
        progress = self.offer("SINGLE")
        self.assertEqual(progress["phase"], "reviewed")
        self.client.request.assert_called_once_with("GET", "/v1/gateways/management")
        self.assertNotIn(NODE["id"], json.dumps(self.client.installation.state))

    def test_deferred_device_setup_needs_no_gateway_or_hardware_access(self):
        self.assertEqual(self.offer("LATER")["phase"], "deferred")
        self.client.request.assert_not_called()

    def test_device_setup_without_read_permission_does_not_block_other_setup(self):
        self.assertEqual(self.offer("DEVICES", ())["phase"], "permission-required")
        self.client.request.assert_not_called()

    def test_individual_setup_calls_existing_management_and_reads_actual_result(self):
        with patch("device_management.guided_devices") as manage:
            progress = self.offer("DEVICES")
        manage.assert_called_once_with(self.client, self.messages)
        self.assertEqual(progress["phase"], "reviewed")
        self.client.request.assert_called_once_with("GET", "/v1/gateways/management")

    def test_interrupted_individual_setup_keeps_pending_progress(self):
        with (
            patch("device_management.guided_devices", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.offer("DEVICES")
        self.assertEqual(
            self.client.installation.state["deviceSetup"]["phase"], "in-progress"
        )
        self.client.request.assert_not_called()

    def test_invalid_device_setup_choice_leaves_state_unchanged(self):
        with self.assertRaisesRegex(ValueError, "E_DEVICE_SETUP_SELECTION"):
            self.offer("invalid")
        self.assertEqual(self.client.installation.state, {})
        self.client.request.assert_not_called()

    def test_pairing_is_available_before_any_device_is_enrolled(self):
        self.messages = json.loads(
            (Path(__file__).resolve().parents[1] / "locales/en.json").read_text(
                encoding="utf-8"
            )
        )
        self.client = Mock()
        self.client.request.return_value = []
        with patch("node_pairing.guided_export") as export:
            self.run_wizard(["PAIR", "0"])
        export.assert_called_once_with(self.client, self.messages)

    def setUp(self):
        self.messages = json.loads(
            (Path(__file__).resolve().parents[1] / "locales/en.json").read_text(
                encoding="utf-8"
            )
        )
        self.client = Mock()
        self.client.request.return_value = [NODE.copy()]

    def run_wizard(self, answers):
        output = io.StringIO()
        with patch("builtins.input", side_effect=answers), patch("sys.stdout", output):
            guided_devices(self.client, self.messages)
        return output.getvalue()

    def test_edit_is_reviewed_revision_bound_and_read_back(self):
        self.run_wizard(["1", "EDIT", "Office", "intermittent", "SAVE", "0"])
        self.assertEqual(self.client.request.call_count, 3)
        self.client.request.assert_any_call(
            "PUT",
            "/v1/gateways/" + NODE["id"] + "/management",
            {
                "revision": NODE["revision"],
                "displayName": "Office",
                "expectedAvailability": "intermittent",
            },
        )
        self.assertEqual(
            self.client.request.call_args.args, ("GET", "/v1/gateways/management")
        )

    def test_cancel_does_not_write(self):
        self.run_wizard(["1", "EDIT", "Office", "always_on", "CANCEL", "0"])
        self.assertTrue(
            all(call.args[0] == "GET" for call in self.client.request.call_args_list)
        )

    def test_revocation_requires_deliberate_confirmation_and_revision(self):
        self.run_wizard(["1", "REMOVE", "REMOVE", "0"])
        self.client.request.assert_any_call(
            "DELETE", "/v1/gateways/" + NODE["id"], {"revision": NODE["revision"]}
        )

    def test_task_policy_is_explicit_reviewed_and_not_service_installation(self):
        output = self.run_wizard(["1", "TASKS", "voice,integration", "APPLY", "0"])
        self.client.request.assert_any_call(
            "PUT",
            "/v1/gateways/" + NODE["id"] + "/tasks",
            {"revision": NODE["revision"], "allowedTasks": ["integration", "voice"]},
        )
        self.assertIn(self.messages["devicesTasksScope"], output)

    def test_unknown_duplicate_and_empty_task_choices_do_not_write(self):
        for choice in ("local_ai", "voice,voice", "", "central", "voice,none"):
            self.client.reset_mock()
            with (
                self.subTest(choice=choice),
                self.assertRaisesRegex(ValueError, "E_DEVICE_TASKS"),
            ):
                self.run_wizard(["1", "TASKS", choice])
            self.assertEqual(self.client.request.call_count, 1)

    def test_revoked_nodes_cannot_be_edited(self):
        self.client.request.return_value = [
            {**NODE, "revokedAt": "2026-11-15T00:00:00Z"}
        ]
        self.run_wizard(["1", "0"])
        self.assertTrue(
            all(call.args[0] == "GET" for call in self.client.request.call_args_list)
        )

    def test_failed_write_propagates_without_success(self):
        self.client.request.side_effect = [
            [NODE],
            ValueError("E_CORE_GATEWAY_MANAGEMENT_CONFLICT"),
        ]
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            self.run_wizard(["1", "EDIT", "Office", "unknown", "SAVE"])
        self.assertEqual(self.client.request.call_count, 2)

    def test_response_rejects_noncanonical_or_missing_identity(self):
        for response in (
            [{**NODE, "id": "../escape"}],
            [{**NODE, "revision": None}],
            [None],
            {},
        ):
            self.client.request.return_value = response
            with (
                self.subTest(response=response),
                self.assertRaises((ValueError, TypeError)),
            ):
                managed_devices(self.client)

    def test_terminal_control_sequences_are_escaped(self):
        self.client.request.return_value = [{**NODE, "displayName": "bad\x1b[2J"}]
        output = self.run_wizard(["0"])
        self.assertNotIn("\x1b", output)
        self.assertIn("\\u001b", output)

    def test_only_exact_device_routes_can_reach_transport(self):
        installation = Mock()
        installation.state = {"backend": "windows-native"}
        client = CoreClient(installation)
        with patch.object(client, "_native_request", return_value={}) as request:
            client.request("PUT", "/v1/gateways/" + NODE["id"] + "/management", {})
            client.request("DELETE", "/v1/gateways/" + NODE["id"], {})
            self.assertEqual(request.call_count, 2)
            for method, route in (
                ("POST", "/v1/gateways/" + NODE["id"] + "/management"),
                ("DELETE", "/v1/gateways/" + NODE["id"] + "/management"),
                ("PUT", "/v1/gateways/" + NODE["id"] + "/../management"),
                ("PUT", "/v1/gateways/" + NODE["id"] + "/management?x=1"),
            ):
                with (
                    self.subTest(route=route),
                    self.assertRaisesRegex(ValueError, "E_API_ROUTE"),
                ):
                    client.request(method, route, {})
            self.assertEqual(request.call_count, 2)
