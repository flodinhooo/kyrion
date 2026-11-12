"""Real pinned loopback TLS with synthetic Core protocol, not app acceptance."""

import json
import ssl
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crypto_support import certificate, private_tls_key
from onboarding import CoreClient, CoreError
from runtime import Installation


class NativeTransport(unittest.TestCase):
    def test_loopback_transport_error_codes_and_redirect_refusal(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.path, self.headers.get("Authorization")))
                if self.path == "/v1/auth/me":
                    payload = json.dumps({"code": "FORBIDDEN"}).encode()
                    self.send_response(403)
                else:
                    payload = b""
                    self.send_response(302)
                    self.send_header(
                        "Location",
                        "http://127.0.0.1:" + str(self.server.server_port) + "/leaked",
                    )
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = None
        try:
            with tempfile.TemporaryDirectory() as directory:
                installation = Installation(
                    Path(directory) / "installation",
                    {"release": "1.2.3", "architecture": "windows/amd64"},
                    "a" * 64,
                    "fixture.test",
                    "127.0.0.1",
                )
                installation.state["backend"] = "windows-native"
                installation.save()
                installation.write("installer.exe", b"synthetic unused worker")
                installation.write("native-manifest.json", "{}")
                key = private_tls_key()
                installation.write("secrets/core-tls.key", key)
                installation.write(
                    "core-cert.pem", certificate("localhost", "127.0.0.1", key)
                )
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(
                    installation.target / "core-cert.pem",
                    installation.target / "secrets/core-tls.key",
                )
                server.socket = context.wrap_socket(server.socket, server_side=True)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                installation.write(
                    "native-runtime.json",
                    json.dumps(
                        {
                            "formatVersion": 1,
                            "hostname": "fixture.test",
                            "address": "127.0.0.1",
                            "ports": {
                                "core": server.server_port,
                                "web": 13000,
                                "postgres": 15432,
                                "caddy": 14443,
                            },
                        }
                    ),
                )
                client = CoreClient(installation)
                client.session = "a" * 43
                with self.assertRaises(CoreError) as error:
                    client.request("GET", "/v1/auth/me")
                self.assertEqual(error.exception.status, 403)
                self.assertEqual(error.exception.code, "FORBIDDEN")
                with self.assertRaises(CoreError) as error:
                    client.request("GET", "/v1/devices")
                self.assertEqual(error.exception.status, 302)
                self.assertEqual(
                    [path for path, _ in received], ["/v1/auth/me", "/v1/devices"]
                )
                self.assertEqual(
                    [authorization for _, authorization in received],
                    ["Bearer " + "a" * 43] * 2,
                )
                with self.assertRaisesRegex(ValueError, "E_API_ROUTE"):
                    client.request("GET", "/unsupported")
                # A different certificate on the same port must not receive credentials.
                (installation.target / "core-cert.pem").write_bytes(
                    certificate("localhost", "127.0.0.1", private_tls_key())
                )
                with self.assertRaisesRegex(ValueError, "E_API"):
                    client.request("GET", "/v1/auth/me")
                self.assertEqual(len(received), 2)
        finally:
            if thread:
                server.shutdown()
            server.server_close()
            if thread:
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
