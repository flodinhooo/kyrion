"""Installer intent/transport fixtures, separate from real Core/DB acceptance."""

import datetime
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity_settings import configure_identity, validate_identity
from linked_onboarding import linked_setup, provider_proof
from onboarding import CoreClient, CoreError
from runtime import Installation


class LinkedOnboarding(unittest.TestCase):
    def test_invitation_join_never_requests_owner_or_creates_another_space(self):
        def api(method, route, body=None, bootstrap=None):
            if route.endswith("setup/status"):
                return {"setupRequired": False}
            if route.endswith("/config"):
                return {"enabled": True}
            if route.endswith("/start"):
                if "/registration/" in route:
                    self.assertEqual(body, {"invitationCode": "i" * 43})
                return self.operation
            if route.endswith("/poll"):
                return {"status": "CONFIRM"}
            if route == "/v1/auth/central/complete":
                raise CoreError("SPACE_ACCESS_REQUIRED", 403)
            if route.endswith("/cancel"):
                return None
            if route.endswith("/registration/complete"):
                self.assertEqual(body["credentials"]["invitationCode"], "i" * 43)
                self.assertNotIn("spaceType", body["credentials"])
                self.assertNotIn("role", body["credentials"])
                return {"sessionToken": "n" * 43}
            if route == "/v1/auth/me":
                return {"roles": ["USER"], "permissions": ["devices:read"]}
            if route == "/v1/auth/central/status":
                return {"linked": True}
            if route == "/v1/space":
                return self.space
            raise AssertionError(route)

        with (
            patch.object(self.client, "request", side_effect=api),
            patch(
                "builtins.input",
                side_effect=["ONLINE", "CHECK", "JOIN", "", "CHECK", "member", "USE"],
            ),
            patch(
                "linked_onboarding.getpass.getpass",
                side_effect=[
                    "i" * 43,
                    "member-local-password",
                    "member-local-password",
                ],
            ),
            patch("linked_onboarding.time.sleep"),
            patch("builtins.print"),
        ):
            user = linked_setup(self.client, self.messages)
        self.assertEqual(user["roles"], ["USER"])
        self.assertEqual(
            self.installation.state["selectedSpace"]["id"], self.space["id"]
        )
        self.assertNotIn(
            "i" * 43, (self.installation.target / "install-state.json").read_text()
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.installation = Installation(
            Path(temporary.name) / "install",
            {"release": "1.2.3", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.installation.write("secrets/bootstrap.secret", "b" * 43)
        self.client = CoreClient(self.installation)
        self.messages = json.loads(
            (Path(__file__).resolve().parents[1] / "locales/en.json").read_text()
        )
        self.space = {
            "id": str(uuid.uuid4()),
            "type": "BUSINESS",
            "status": "ACTIVE",
            "name": "Fixture company",
        }
        self.operation = {
            "operationToken": "o" * 43,
            "verificationUri": "https://issuer.example/device",
            "userCode": "TEST-CODE",
            "expiresAt": (
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=5)
            ).isoformat(),
            "interval": 1,
        }

    def test_new_linked_identity_and_explicit_space_consent(self):
        def api(method, route, body=None, bootstrap=None):
            if route.endswith("setup/status"):
                return {"setupRequired": True}
            if route.endswith("/config"):
                return {"enabled": True}
            if route.endswith("/start"):
                self.assertEqual(bootstrap, "b" * 43)
                return self.operation
            if route.endswith("/poll"):
                return {"status": "CONFIRM"}
            if route.endswith("/complete"):
                self.assertEqual(body["credentials"]["spaceType"], "BUSINESS")
                self.assertEqual(
                    body["credentials"]["password"], "local-offline-password"
                )
                return {"sessionToken": "s" * 43}
            if route == "/v1/auth/me":
                return {"id": "same-linked-owner", "roles": ["OWNER"]}
            if route == "/v1/auth/central/status":
                return {"linked": True}
            if route == "/v1/space":
                return self.space
            raise AssertionError(route)

        with (
            patch.object(self.client, "request", side_effect=api) as calls,
            patch(
                "builtins.input",
                side_effect=["CHECK", "owner", "BUSINESS", "Fixture company", "USE"],
            ),
            patch(
                "linked_onboarding.getpass.getpass",
                return_value="local-offline-password",
            ),
            patch("linked_onboarding.time.sleep"),
            patch("builtins.print"),
        ):
            linked_setup(self.client, self.messages)
        self.assertEqual(
            self.installation.state["selectedSpace"],
            {"id": self.space["id"], "type": "BUSINESS"},
        )
        self.assertEqual(self.client.session, "s" * 43)
        persisted = (self.installation.target / "install-state.json").read_text()
        for secret in (
                "local-offline-password",
                "s" * 43,
                "o" * 43,
                "same-linked-owner",
        ):
            self.assertNotIn(secret, persisted)
        self.assertFalse(
            any(call.args[1] == "/v1/auth/setup" for call in calls.call_args_list)
        )

    def test_existing_offline_access_reuses_link_and_current_space_without_provider(
        self,
    ):
        self.client.login_or_setup = MagicMock(return_value={"roles": ["USER"]})
        with (
            patch.object(
                self.client,
                "request",
                side_effect=[{"setupRequired": False}, {"linked": True}, self.space],
            ) as calls,
            patch("builtins.input", side_effect=["OFFLINE", "existing-user", "USE"]),
            patch("linked_onboarding.getpass.getpass", return_value="offline-password"),
            patch("builtins.print"),
        ):
            linked_setup(self.client, self.messages)
        self.assertFalse(
            any(
                call.args[1].endswith(("/start", "/poll", "/complete"))
                for call in calls.call_args_list
            )
        )
        self.client.login_or_setup.assert_called_once_with(
            "existing-user", "offline-password"
        )

    def test_cancelled_provider_flow_is_cancelled_without_creating_a_user(self):
        with (
            patch.object(
                self.client, "request", side_effect=[self.operation, None]
            ) as calls,
            patch("builtins.input", return_value="CANCEL"),
            patch("builtins.print"),
            self.assertRaisesRegex(ValueError, "E_IDENTITY_CANCELLED"),
            provider_proof(self.client, self.messages, True),
        ):
            self.fail("Cancelled operation must not yield")
        self.assertEqual(calls.call_args.args[1], "/v1/auth/central/setup/cancel")

    def test_disabled_provider_does_not_create_unlinked_owner(self):
        with (
            patch.object(
                self.client,
                "request",
                side_effect=[{"setupRequired": True}, {"enabled": False}],
            ) as calls,
            self.assertRaisesRegex(ValueError, "E_IDENTITY_NOT_CONFIGURED"),
        ):
            linked_setup(self.client, self.messages)
        self.assertEqual(calls.call_count, 2)
        self.assertEqual(self.installation.state["ownerSetup"], "not-verified")

    def test_public_provider_settings_are_validated_and_cannot_change_on_resume(self):
        value = {
            "issuer": "https://issuer.example/realm",
            "clientId": "kyrion-local",
            "allowLoopbackHttp": False,
        }
        configure_identity(self.installation, value)
        configure_identity(self.installation, value)
        with self.assertRaisesRegex(ValueError, "E_IDENTITY_CONFIG_CHANGED"):
            configure_identity(
                self.installation, {**value, "issuer": "https://other.example/realm"}
            )
        for issuer in (
                "http://remote.example/realm",
                "https://user:pass@issuer.example/realm",
                "https://issuer.example/realm\nINJECT=value",
                "https://issuer.example/realm?query=true",
        ):
            with (
                self.subTest(issuer=issuer),
                self.assertRaisesRegex(ValueError, "E_IDENTITY_CONFIG"),
            ):
                validate_identity({**value, "issuer": issuer})
