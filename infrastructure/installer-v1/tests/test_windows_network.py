"""Actual Windows TCP SDK and local TLS transport; no service registration."""

import os
import socket
import ssl
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crypto_support import certificate, private_tls_key
from native_web_transport import WebTransport
from windows_network import assert_peer


@unittest.skipUnless(os.name == "nt", "Windows TCP ownership SDK")
class Transport(unittest.TestCase):
    def test_established_peer_and_wrong_pid(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with socket.create_connection(listener.getsockname()) as client:
                server, _ = listener.accept()
                with server:
                    assert_peer(client, os.getpid())
                    with self.assertRaisesRegex(ValueError, "E_NATIVE_TCP_OWNER"):
                        assert_peer(client, os.getpid() + 100000)

    def test_tls_forwards_only_to_expected_owner(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"isolated transport fixture")

            def log_message(self, *_):
                pass

        class Child:
            pid = os.getpid()

            def poll(self):
                return None

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "data/web-tls").mkdir(parents=True)
                key = private_tls_key()
                (root / "data/web-tls/key.pem").write_bytes(key)
                (root / "web-cert.pem").write_bytes(
                    certificate("localhost", "127.0.0.1", key)
                )
                child = Child()
                with WebTransport(root, 0, server.server_port, child) as proxy:
                    context = ssl.create_default_context(
                        cafile=str(root / "web-cert.pem")
                    )

                    def request():
                        with (
                            socket.create_connection(
                                proxy.server.server_address, timeout=5
                            ) as raw,
                            context.wrap_socket(
                                raw, server_hostname="localhost"
                            ) as secured,
                        ):
                            secured.sendall(
                                b"GET / HTTP/1.1\r\nHost: localhost\r\nAuthorization: fixture-token\r\nConnection: close\r\n\r\n"
                            )
                            data = b""
                            while chunk := secured.recv(65536):
                                data += chunk
                            return data

                    self.assertIn(b"isolated transport fixture", request())
                    child.pid += 100000
                    try:
                        response = request()
                    except OSError:
                        response = b""
                    self.assertNotIn(b"200 OK", response)
                    self.assertEqual(received, ["fixture-token"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
