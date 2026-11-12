"""Synthetic loopback OIDC authority with real TLS/JWT verification, not Keycloak."""

from __future__ import annotations

import base64
import json
import secrets
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from crypto_support import certificate, private_tls_key
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12


def encoded(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class IdentityFixture:
    def __init__(self, root):
        self.approved = False
        self.subject = "synthetic-linked-owner"
        self.codes = set()
        self.closed = False
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def send(self, status, value):
                data = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/realm/.well-known/openid-configuration":
                    self.send(
                        200,
                        {
                            "issuer": owner.issuer,
                            "device_authorization_endpoint": owner.issuer + "/device",
                            "token_endpoint": owner.issuer + "/token",
                            "jwks_uri": owner.issuer + "/keys",
                        },
                    )
                elif self.path == "/realm/keys":
                    numbers = owner.key.public_key().public_numbers()
                    self.send(
                        200,
                        {
                            "keys": [
                                {
                                    "kty": "RSA",
                                    "kid": "synthetic-key",
                                    "use": "sig",
                                    "alg": "RS256",
                                    "n": encoded(
                                        numbers.n.to_bytes(
                                            (numbers.n.bit_length() + 7) // 8, "big"
                                        )
                                    ),
                                    "e": encoded(numbers.e.to_bytes(3, "big")),
                                }
                            ]
                        },
                    )
                else:
                    self.send(404, {"error": "fixture_endpoint"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    self.send(400, {"error": "invalid_request"})
                    return
                fields = parse_qs(self.rfile.read(length).decode())
                if (
                    fields.get("client_id") != ["kyrion-local"]
                    or "client_secret" in fields
                ):
                    self.send(400, {"error": "invalid_client"})
                elif self.path == "/realm/device":
                    code = secrets.token_urlsafe(32)
                    owner.codes.add(code)
                    self.send(
                        200,
                        {
                            "device_code": code,
                            "user_code": "ISOLATED-CODE",
                            "verification_uri": owner.issuer + "/verify",
                            "expires_in": 600,
                            "interval": 1,
                        },
                    )
                elif (
                    self.path == "/realm/token"
                    and fields.get("device_code", [None])[0] in owner.codes
                ):
                    if not owner.approved:
                        self.send(400, {"error": "authorization_pending"})
                    else:
                        now = int(time.time())
                        header = encoded(
                            json.dumps(
                                {"alg": "RS256", "kid": "synthetic-key"}
                            ).encode()
                        )
                        payload = encoded(
                            json.dumps(
                                {
                                    "iss": owner.issuer,
                                    "sub": owner.subject,
                                    "aud": "kyrion-local",
                                    "iat": now - 1,
                                    "exp": now + 300,
                                }
                            ).encode()
                        )
                        message = (header + "." + payload).encode()
                        signature = owner.key.sign(
                            message, padding.PKCS1v15(), hashes.SHA256()
                        )
                        self.send(
                            200,
                            {"id_token": message.decode() + "." + encoded(signature)},
                        )
                else:
                    self.send(400, {"error": "invalid_grant"})

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.issuer = "https://127.0.0.1:" + str(self.server.server_port) + "/realm"
        key = private_tls_key()
        cert = certificate("localhost", "127.0.0.1", key)
        (root / "issuer.key").write_bytes(key)
        (root / "issuer.pem").write_bytes(cert)
        self.truststore = root / "issuer-trust.p12"
        self.truststore.write_bytes(
            pkcs12.serialize_java_truststore(
                [
                    pkcs12.PKCS12Certificate(
                        x509.load_pem_x509_certificate(cert), b"fixture-issuer"
                    )
                ],
                serialization.BestAvailableEncryption(b"isolated-test-store"),
            )
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(root / "issuer.pem", root / "issuer.key")
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        if not self.closed:
            self.closed = True
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
