"""Foreground installer choices with injected Core/agent operations, no hardware."""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from package import source_file

sys.path.insert(
    0, str(source_file(ROOT, "kyrion_gateway_agent/__init__.py").parent.parent)
)
import node_entry
from crypto_support import certificate, private_tls_key


class NodeEntryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.args = SimpleNamespace(
            prepare_node=True,
            node_config=root / "node/agent.json",
            node_url="https://127.0.0.1:8443",
            node_token_file=root / "code",
            node_certificate=root / "cert.pem",
        )
        self.args.node_token_file.write_text("a" * 43)
        self.args.node_certificate.write_bytes(
            certificate("localhost", "127.0.0.1", private_tls_key())
        )
        self.messages = json.loads(
            (ROOT / "locales/en.json").read_text(encoding="utf-8")
        )

    @contextlib.contextmanager
    def synthetic_linux(self, answer):
        with (
            patch("node_entry.sys.platform", "linux"),
            patch("host.inventory", return_value={"system": "synthetic Linux"}),
            patch(
                "kyrion_gateway_agent.health.platform_identity",
                return_value={"hostname": "synthetic"},
            ),
            patch("builtins.input", return_value=answer),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            yield output

    def test_cancelling_pairing_does_not_enroll_or_publish_credentials(self):
        with (
            self.synthetic_linux("CANCEL") as output,
            patch("kyrion_gateway_agent.enrollment.enroll_prepared") as enroll,
        ):
            self.assertEqual(node_entry.run(self.args, self.messages), 0)
        enroll.assert_not_called()
        self.assertNotIn("a" * 43, output.getvalue())
        self.assertFalse(self.args.node_config.parent.exists())

    def test_confirmed_pairing_calls_existing_protected_protocol_and_never_claims_a_service(
        self,
    ):
        node = SimpleNamespace(node_id="738f6172-e783-4986-8a5c-7e4c478fca03")
        with (
            self.synthetic_linux("PAIR") as output,
            patch(
                "kyrion_gateway_agent.enrollment.enroll_prepared", return_value=node
            ) as enroll,
        ):
            node_entry.run(self.args, self.messages)
        enroll.assert_called_once()
        self.assertEqual(enroll.call_args.args, (self.args.node_config.absolute(),))
        self.assertEqual(
            enroll.call_args.kwargs["token_file"], self.args.node_token_file
        )
        self.assertEqual(
            enroll.call_args.kwargs["expected_ca_sha256"],
            hashlib.sha256(self.args.node_certificate.read_bytes()).hexdigest(),
        )
        self.assertIn('"serviceInstalled": false', output.getvalue())
        self.assertNotIn("a" * 43, output.getvalue())

    def test_partial_connection_parameters_are_rejected_before_pairing(self):
        self.args.node_certificate = None
        with (
            self.synthetic_linux("PAIR"),
            patch("kyrion_gateway_agent.enrollment.enroll_prepared") as enroll,
            self.assertRaisesRegex(ValueError, "E_NODE_ENROLL_INPUT"),
        ):
            node_entry.run(self.args, self.messages)
        enroll.assert_not_called()

    def test_windows_prepared_storage_is_not_misrepresented_as_supported(self):
        with (
            patch("node_entry.sys.platform", "win32"),
            self.assertRaisesRegex(ValueError, "E_AGENT_PLATFORM"),
        ):
            node_entry.run(self.args, self.messages)

    def test_heartbeat_does_not_poll_or_execute_commands(self):
        self.args.prepare_node = False
        self.args.node_config.parent.mkdir()
        self.args.node_config.write_text("synthetic protected configuration")
        self.args.node_url = self.args.node_token_file = self.args.node_certificate = (
            None
        )
        config = SimpleNamespace(
            local_only=True,
            ca_certificate="fixture",
            ca_sha256="b" * 64,
            node_id="fixture",
        )
        with (
            self.synthetic_linux("HEARTBEAT"),
            patch("kyrion_gateway_agent.enrollment.private_directory"),
            patch("kyrion_gateway_agent.enrollment.read_private"),
            patch("kyrion_gateway_agent.config.AgentConfig.load", return_value=config),
            patch(
                "kyrion_gateway_agent.health.collect_health",
                return_value={"synthetic": True},
            ),
            patch("kyrion_gateway_agent.client.heartbeat") as heartbeat,
            patch("kyrion_gateway_agent.client.next_command") as commands,
        ):
            node_entry.run(self.args, self.messages)
        heartbeat.assert_called_once_with(config, {"synthetic": True})
        commands.assert_not_called()
