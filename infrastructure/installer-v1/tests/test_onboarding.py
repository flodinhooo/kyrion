"""Existing Core contract tests with synthetic responses, no users/providers."""

import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from onboarding import (
    CoreClient,
    guided_home_assistant,
    link_existing_identity,
    selected_indices,
)
from runtime import Installation


class OnboardingTests(unittest.TestCase):
    def test_device_selection_rejects_duplicates_and_out_of_range(self):
        self.assertEqual(selected_indices("alle", 3), [0, 1, 2])
        self.assertEqual(selected_indices("none", 3), [])
        self.assertEqual(selected_indices("3,1", 3), [2, 0])
        for value in ("0", "4", "1,1", "-1", "1.5", "unknown"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                selected_indices(value, 3)

    def test_skipping_home_assistant_has_no_provider_request(self):
        with (
            patch("builtins.input", return_value="skip"),
            patch.object(self.client, "request") as request,
        ):
            guided_home_assistant(self.client, {"haConfigure": "Configure"})
        request.assert_not_called()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / "installation"
        self.installation = Installation(
            target,
            {"release": "1.2.3", "architecture": "linux/arm64"},
            "a" * 64,
            "kyrion.home.arpa",
            "192.168.1.2",
        )
        self.client = CoreClient(self.installation)

    def test_password_and_session_are_stdin_only(self):
        self.client.session = "s" * 43
        result = subprocess.CompletedProcess([], 0, '{"ok":true}\n200', "")
        with patch("onboarding.subprocess.run", return_value=result) as run:
            self.assertEqual(
                self.client.request(
                    "POST", "/v1/auth/login", {"password": "private-secret"}
                ),
                {"ok": True},
            )
            arguments = run.call_args.args[0]
            self.assertNotIn("private-secret", " ".join(arguments))
            self.assertNotIn(self.client.session, " ".join(arguments))
            self.assertIn("private-secret", run.call_args.kwargs["input"])
            self.assertIn(self.client.session, run.call_args.kwargs["input"])
            self.assertNotIn("private-secret", self.installation.path.read_text())

    @unittest.skipUnless(
        shutil.which("curl"), "curl required for real stdin-config transport"
    )
    def test_actual_curl_config_preserves_json_and_authorization(self):
        received = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received["body"] = json.loads(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )
                received["authorization"] = self.headers.get("Authorization")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *args):
                pass

        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except OSError:
            self.skipTest("Host prohibits isolated loopback fixture")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        real_run = subprocess.run

        def transport(arguments, **kwargs):
            kwargs["input"] = kwargs["input"].replace(
                "127.0.0.1:8080", "127.0.0.1:" + str(server.server_port)
            )
            return real_run(["curl", "--config", "-"], **kwargs)

        body = {"password": 'synthetic-quote"-backslash\\-unicode-\u00e4'}
        self.client.session = "s" * 43
        try:
            with patch("onboarding.subprocess.run", side_effect=transport):
                self.assertEqual(
                    self.client.request("POST", "/v1/auth/login", body), {"ok": True}
                )
            self.assertEqual(received["body"], body)
            self.assertEqual(received["authorization"], "Bearer " + self.client.session)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_arbitrary_control_route_not_available(self):
        with self.assertRaisesRegex(ValueError, "E_API_ROUTE"):
            self.client.request("POST", "/v1/devices/arbitrary-command", {})

    def test_existing_installation_logs_in_without_creating_user_or_space(self):
        with patch.object(
            self.client,
            "request",
            side_effect=[
                {"setupRequired": False},
                {"sessionToken": "s" * 43},
                {"id": "existing-user"},
            ],
        ) as request:
            self.client.login_or_setup("owner", "local-password")
            self.assertEqual(request.call_args_list[1].args[1], "/v1/auth/login")
            self.assertFalse(
                any(call.args[1] == "/v1/auth/setup" for call in request.call_args_list)
            )
            self.assertEqual(self.installation.state["ownerSetup"], "authenticated")

    def test_setup_uses_existing_core_home_contract(self):
        (self.installation.target / "secrets").mkdir()
        (self.installation.target / "secrets/bootstrap.secret").write_text("b" * 43)
        with patch.object(
            self.client,
            "request",
            side_effect=[
                {"setupRequired": True},
                {"sessionToken": "s" * 43},
                {"id": "owner"},
            ],
        ) as request:
            self.client.login_or_setup("owner", "local-password", "My Home")
            setup = request.call_args_list[1]
            self.assertEqual(setup.args[1], "/v1/auth/setup")
            self.assertEqual(setup.args[2]["spaceType"], "HOME")
            self.assertEqual(setup.args[2]["spaceName"], "My Home")
            self.assertEqual(setup.kwargs["bootstrap"], "b" * 43)

    def test_business_setup_uses_existing_core_space_type(self):
        (self.installation.target / "secrets").mkdir()
        (self.installation.target / "secrets/bootstrap.secret").write_text("b" * 43)
        with patch.object(
            self.client,
            "request",
            side_effect=[
                {"setupRequired": True},
                {"sessionToken": "s" * 43},
                {"id": "owner"},
            ],
        ) as request:
            self.client.login_or_setup(
                "owner", "local-password", "My Business", "BUSINESS"
            )
            self.assertEqual(request.call_args_list[1].args[2]["spaceType"], "BUSINESS")

    def test_failed_ha_probe_cannot_store_connection(self):
        with patch.object(
            self.client,
            "request",
            return_value={"reachable": True, "authenticated": False},
        ) as request:
            with self.assertRaisesRegex(ValueError, "E_HA_PROBE"):
                self.client.connect_home_assistant(
                    "http://192.168.1.4:8123", "private-token"
                )
            self.assertEqual(request.call_count, 1)

    def test_ha_connect_follows_real_authenticated_probe(self):
        with patch.object(
            self.client,
            "request",
            side_effect=[
                {"reachable": True, "authenticated": True},
                {"connected": True, "importedDeviceCount": 3},
            ],
        ) as request:
            result = self.client.connect_home_assistant(
                "http://192.168.1.4:8123", "private-token"
            )
            self.assertEqual(result["importedDeviceCount"], 3)
            self.assertEqual(
                request.call_args_list[0].args[1],
                "/v1/integrations/home-assistant/probe",
            )
            self.assertEqual(
                request.call_args_list[1].args[1],
                "/v1/integrations/home-assistant/connect",
            )

    def test_api_error_does_not_expose_provider_output(self):
        result = subprocess.CompletedProcess(
            [], 0, '{"code":"UNAUTHENTICATED","secret":"private"}\n401', "private"
        )
        with (
            patch("onboarding.subprocess.run", return_value=result),
            self.assertRaisesRegex(ValueError, "^UNAUTHENTICATED$"),
        ):
            self.client.request("GET", "/v1/auth/me")

    def test_logout_clears_session_even_if_core_unavailable(self):
        self.client.session = "s" * 43
        with (
            patch.object(self.client, "request", side_effect=ValueError("E_API")),
            self.assertRaises(ValueError),
        ):
            self.client.close()
        self.assertIsNone(self.client.session)

    def test_skipped_identity_operation_is_cancelled_without_linking(self):
        messages = {
            key: key for key in ("centralBrowser", "centralCode", "centralCheck")
        }
        with (
            patch.object(
                self.client,
                "request",
                side_effect=[
                    {"linked": False},
                    {
                        "operationToken": "o" * 43,
                        "verificationUri": "https://auth.example.test/verify",
                        "userCode": "TEST-CODE",
                    },
                    None,
                ],
            ) as request,
            patch("builtins.input", return_value="skip"),
            patch("builtins.print"),
        ):
            link_existing_identity(self.client, "local-password", messages)
            self.assertEqual(request.call_args.args[1], "/v1/auth/central/cancel")
            self.assertNotIn("centralIdentity", self.installation.state)

    def test_locale_hardware_selection_text_is_translated(self):
        root = Path(__file__).resolve().parents[1]
        en = json.loads((root / "locales/en.json").read_text(encoding="utf-8"))
        de = json.loads((root / "locales/de.json").read_text(encoding="utf-8"))
        self.assertNotEqual(en["hardwareHelp"], de["hardwareHelp"])


if __name__ == "__main__":
    unittest.main()
