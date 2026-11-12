"""Actual Windows TCP/TLS to a separate child peer; no service registration."""

import http.client
import os
import socket
import ssl
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crypto_support import certificate, private_tls_key
from native_web_transport import WebTransport
from socket_owner_fixture import owner_server
from windows_network import assert_peer


@unittest.skipUnless(os.name == "nt", "Windows TCP ownership SDK")
class Transport(unittest.TestCase):
    def test_established_peer_and_wrong_pid(self):
        # Same-process accepted sockets intermittently report non-established
        # states on this Windows build. Match the actual separate-child topology;
        # never weaken the production validator to accept those snapshots.
        with (
            owner_server() as (child, port),
            socket.create_connection(("127.0.0.1", port)) as client,
        ):
            assert_peer(client, child.pid)
            with self.assertRaisesRegex(ValueError, "E_NATIVE_TCP_OWNER"):
                assert_peer(client, os.getpid())

    def test_tls_forwards_only_to_expected_owner(self):
        with (
            owner_server() as (child, port),
            tempfile.TemporaryDirectory() as directory,
        ):
            root = Path(directory)
            (root / "data/web-tls").mkdir(parents=True)
            key = private_tls_key()
            (root / "data/web-tls/key.pem").write_bytes(key)
            (root / "web-cert.pem").write_bytes(
                certificate("localhost", "127.0.0.1", key)
            )
            expected = SimpleNamespace(pid=child.pid, poll=child.poll)
            with WebTransport(root, 0, port, expected) as proxy:
                context = ssl.create_default_context(cafile=str(root / "web-cert.pem"))

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
                expected.pid = os.getpid()
                try:
                    response = request()
                except OSError:
                    response = b""
                self.assertNotIn(b"200 OK", response)
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    connection.request("GET", "/count")
                    self.assertEqual(connection.getresponse().read(64), b"1")
                finally:
                    connection.close()
