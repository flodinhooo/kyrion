"""Existing provider selection and real local CLI journal; OS/SSO calls injected."""

import contextlib
import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import guided
from bundle import ReviewedBundle
from identity_settings import (
    DEFAULT_CLIENT_ID,
    DEFAULT_ISSUER,
    configure_identity,
    select_identity,
)
from runtime import Installation


class IdentitySettings(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.saved = {
            "issuer": "https://identity.example.test/realms/fixture",
            "clientId": "fixture-local",
            "allowLoopbackHttp": False,
        }

    def test_fresh_defaults_and_explicit_operator_selection_preserve_existing_contract(
        self,
    ):
        self.assertEqual(
            select_identity(None, None),
            {
                "issuer": DEFAULT_ISSUER,
                "clientId": DEFAULT_CLIENT_ID,
                "allowLoopbackHttp": False,
            },
        )
        self.assertEqual(
            select_identity(self.saved["issuer"], self.saved["clientId"]), self.saved
        )
        self.assertEqual(
            select_identity(None, "other-public-client")["issuer"], DEFAULT_ISSUER
        )

    def test_saved_provider_survives_missing_command_arguments_without_mutation(self):
        before = copy.deepcopy(self.saved)
        selected = select_identity(None, None, saved=self.saved)
        self.assertEqual(selected, self.saved)
        selected["issuer"] = DEFAULT_ISSUER
        self.assertEqual(self.saved, before)
        self.assertEqual(
            select_identity(self.saved["issuer"], None, saved=self.saved), self.saved
        )

    def test_conflicting_explicit_arguments_cannot_repoint_existing_identity(self):
        for issuer, client in (
            (DEFAULT_ISSUER, None),
            (None, DEFAULT_CLIENT_ID),
            (DEFAULT_ISSUER, DEFAULT_CLIENT_ID),
        ):
            with (
                self.subTest(issuer=issuer, client=client),
                self.assertRaisesRegex(ValueError, "E_IDENTITY_CONFIG_CHANGED"),
            ):
                select_identity(issuer, client, saved=self.saved)

    def test_invalid_saved_provider_is_not_replaced_with_product_default(self):
        for saved in (
            {**self.saved, "clientSecret": "private fixture"},
            {**self.saved, "allowLoopbackHttp": 0},
            {**self.saved, "issuer": "http://identity.example.test/realm"},
        ):
            with self.assertRaisesRegex(ValueError, "E_IDENTITY_CONFIG"):
                select_identity(None, None, saved=saved)

    def cli(self, *, conflict=False):
        target = self.root / "installation"
        installation = Installation(
            target,
            {"release": "1.2.3", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        configure_identity(installation, self.saved)
        original = (target / "identity-provider.json").read_bytes()
        manifest = {
            "schemaVersion": 1,
            "release": "1.2.3",
            "architecture": "linux/amd64",
            "artifacts": [
                {"name": name, "bytes": 1, "sha256": "b" * 64}
                for name in (
                    "kyrion-core-amd64.tar",
                    "kyrion-web-amd64.tar",
                    "postgres-amd64.tar",
                    "caddy-amd64.tar",
                )
            ],
        }
        arguments = [
            "guided",
            "--target",
            str(target),
            "--bundle",
            str(self.root / "public-bundle"),
            "--public-key",
            str(self.root / "public.pem"),
        ]
        if conflict:
            arguments += ["--identity-issuer", DEFAULT_ISSUER]
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(sys, "argv", arguments),
            patch("sys.stdin.isatty", return_value=True),
            patch(
                "builtins.input",
                side_effect=["en", "resume", "fixture.test", "127.0.0.1", "CANCEL"],
            ),
            patch(
                "guided.inventory",
                return_value={
                    "system": "Linux",
                    "architecture": "amd64",
                    "candidateProvisioning": True,
                },
            ),
            patch("guided.validate_inputs"),
            patch(
                "guided.authenticated_review",
                return_value=ReviewedBundle(manifest, "a" * 64),
            ),
            patch("guided.provision") as provision,
            patch("guided.guided_setup") as setup,
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            result = guided.main()
        provision.assert_not_called()
        setup.assert_not_called()
        self.assertEqual((target / "identity-provider.json").read_bytes(), original)
        return result, output.getvalue(), errors.getvalue()

    def test_terminal_resume_reviews_saved_provider_without_repeated_issuer_flags(self):
        result, output, _errors = self.cli()
        self.assertEqual(result, 0)
        self.assertIn(self.saved["issuer"], output)
        self.assertIn(self.saved["clientId"], output)

    def test_terminal_conflict_refuses_before_runtime_or_account_mutation(self):
        result, _output, errors = self.cli(conflict=True)
        self.assertEqual(result, 2)
        self.assertIn("E_IDENTITY_CONFIG_CHANGED", errors)
