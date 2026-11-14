"""Real loopback HTTP/TLS transport with a synthetic Core protocol fixture."""

import contextlib
import hashlib
import json
import secrets
import shutil
import ssl
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kyrion_gateway_agent import client
from kyrion_gateway_agent.config import AgentConfig


@contextlib.contextmanager
def server(*, certificate=None, key=None, protocol=2, redirect=None, oversized=False):
    calls = []
    node = str(uuid.uuid4())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_arguments):
            pass

        def do_GET(self):
            calls.append(("GET", self.path))
            self.reply(
                {
                    "formatVersion": 1,
                    "enrollmentProtocol": protocol,
                    "clientCredential": True,
                    "acknowledgementWithinOriginalExpiry": True,
                }
            )

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            calls.append(("POST", self.path))
            if redirect:
                self.send_response(307)
                self.send_header("Location", redirect)
                self.end_headers()
            elif self.path.endswith("/enroll"):
                self.reply({"nodeId": node, "gatewayToken": body["nodeCredential"]})
            else:
                self.reply({"data": "x" * (1024**2 + 1)} if oversized else {})

        def reply(self, value):
            raw = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    if certificate is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        instance.socket = context.wrap_socket(instance.socket, server_side=True)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance.server_port, calls
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


@pytest.fixture
def tls_material(tmp_path):
    executable = shutil.which("openssl")
    if executable is None:
        pytest.skip("OpenSSL CLI required for real disposable TLS certificates")
    certificate, key = tmp_path / "certificate.pem", tmp_path / "private.key"
    subprocess.run(
        [
            executable,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    key.chmod(0o600)
    return certificate, key, hashlib.sha256(certificate.read_bytes()).hexdigest()


def test_prepared_enrollment_uses_verified_tls_and_capability_before_credentials(tls_material):
    certificate, key, digest = tls_material
    with server(certificate=certificate, key=key) as (port, calls):
        credential = secrets.token_urlsafe(32)
        result = client.enroll(
            f"https://localhost:{port}",
            "Synthetic-one-use-code",
            {"hostname": "fixture", "osName": "fixture", "osVersion": "1", "architecture": "amd64"},
            node_credential=credential,
            ca_certificate=str(certificate),
            ca_sha256=digest,
        )
        assert secrets.compare_digest(result.gateway_token, credential)
        assert str(uuid.UUID(result.node_id)) == result.node_id
        assert calls == [
            ("GET", "/v1/gateway-agent/enrollment-capabilities"),
            ("POST", "/v1/gateway-agent/enroll"),
        ]


def test_legacy_core_does_not_receive_prepared_pairing_code(tls_material):
    certificate, key, digest = tls_material
    with server(certificate=certificate, key=key, protocol=1) as (port, calls):
        with pytest.raises(client.CoreRequestError, match="E_AGENT_ENROLLMENT_UPGRADE_REQUIRED"):
            client.enroll(
                f"https://localhost:{port}",
                "Synthetic-code",
                {},
                node_credential=secrets.token_urlsafe(32),
                ca_certificate=str(certificate),
                ca_sha256=digest,
            )
        assert calls == [("GET", "/v1/gateway-agent/enrollment-capabilities")]


def test_prepared_enrollment_never_sends_credentials_over_plain_http():
    with server() as (port, calls):
        with pytest.raises(client.CoreRequestError, match="E_AGENT_TLS_REQUIRED"):
            client.enroll(
                f"http://localhost:{port}",
                "Synthetic-code",
                {},
                node_credential=secrets.token_urlsafe(32),
            )
        assert calls == []


def test_hostname_verification_and_changed_ca_are_not_bypassed(tls_material):
    certificate, key, digest = tls_material
    with server(certificate=certificate, key=key) as (port, calls):
        with pytest.raises(client.CoreRequestError):
            client.enroll(
                f"https://127.0.0.1:{port}",
                "Synthetic-code",
                {},
                node_credential=secrets.token_urlsafe(32),
                ca_certificate=str(certificate),
                ca_sha256=digest,
            )
        certificate.write_bytes(certificate.read_bytes() + b"\n")
        with pytest.raises(client.CoreRequestError, match="E_AGENT_TLS_CONFIGURATION"):
            client.enroll(
                f"https://localhost:{port}",
                "Synthetic-code",
                {},
                node_credential=secrets.token_urlsafe(32),
                ca_certificate=str(certificate),
                ca_sha256=digest,
            )
        assert calls == []


def test_authenticated_requests_never_follow_redirects():
    with server() as (destination, forwarded):
        with server(redirect=f"http://localhost:{destination}/forwarded") as (port, _calls):
            config = AgentConfig(f"http://localhost:{port}", str(uuid.uuid4()), "Synthetic-token")
            with pytest.raises(client.CoreRequestError):
                client.next_command(config)
        assert forwarded == []


def test_response_size_is_bounded():
    with server(oversized=True) as (port, _calls):
        config = AgentConfig(f"http://localhost:{port}", str(uuid.uuid4()), "Synthetic-token")
        with pytest.raises(client.CoreRequestError, match="E_AGENT_RESPONSE_LIMIT"):
            client.next_command(config)


def test_existing_runtime_requests_reuse_the_pinned_ca(tls_material):
    certificate, key, digest = tls_material
    with server(certificate=certificate, key=key) as (port, calls):
        config = AgentConfig(
            f"https://localhost:{port}",
            str(uuid.uuid4()),
            "Synthetic-token",
            str(certificate),
            digest,
        )
        assert client.next_command(config) is None
        assert calls == [("POST", "/v1/gateway-agent/commands/next")]


def test_config_preserves_tls_metadata_without_disclosing_credential_in_repr(tmp_path):
    config = AgentConfig(
        "https://localhost",
        str(uuid.uuid4()),
        "Synthetic-sensitive-token",
        str(tmp_path / "ca.pem"),
        "a" * 64,
    )
    path = tmp_path / "agent.json"
    config.save(path)
    assert AgentConfig.load(path) == config
    assert config.gateway_token not in repr(config)
    value = json.loads(path.read_bytes())
    value["ca_sha256"] = None
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="E_AGENT_TLS_CONFIGURATION"):
        AgentConfig.load(path)
