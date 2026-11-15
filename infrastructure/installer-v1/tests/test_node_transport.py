"""Source configuration checks; actual Caddy acceptance has its own fixture."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from node_transport import AGENT_PATHS, agent_handle


class NodeTransportTests(unittest.TestCase):
    def test_only_existing_agent_protocol_paths_are_routed(self):
        result = agent_handle("core:8080")
        self.assertIn("not remote_ip", result)
        self.assertNotIn("forwarded", result)
        self.assertNotIn("/v1/auth", result)
        self.assertNotIn("/v1/gateways/*", result)
        self.assertNotIn("/v1/voice-satellite/*", AGENT_PATHS)
        self.assertNotIn("0.0.0.0/0", result)

    def test_native_transport_preserves_upstream_tls_verification(self):
        path = Path.cwd() / "core-cert.pem"
        result = agent_handle("https://127.0.0.1:8080", path)
        self.assertIn("tls_trust_pool file", result)
        self.assertIn(path.as_posix(), result)
        self.assertNotIn("insecure", result)

    def test_arbitrary_upstreams_and_missing_trust_are_refused(self):
        for upstream, certificate in (
            ("http://127.0.0.1:8080", None),
            ("https://example.com", None),
            ("https://127.0.0.1:65536", Path.cwd()),
            ("https://127.0.0.1:8080", None),
            ("core:8080", Path.cwd()),
            ("core:8080\nrespond 200", None),
            ("https://127.0.0.1:8080", Path("relative.pem")),
        ):
            with self.subTest(upstream=upstream), self.assertRaises(ValueError):
                agent_handle(upstream, certificate)
