"""Real Caddy/TLS acceptance with synthetic upstreams and no device actions."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import http.server
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from crypto_support import certificate, private_tls_key
from node_transport import agent_handle


def port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def exercise(caddy: Path, digest: str, work: Path, public_peer: str | None) -> dict:
    if not caddy.is_file() or hashlib.sha256(caddy.read_bytes()).hexdigest() != digest:
        raise ValueError("E_FIXTURE_CADDY_INTEGRITY")
    with (
        tempfile.TemporaryDirectory(prefix="agent-proxy-", dir=work) as directory,
        contextlib.ExitStack() as stack,
    ):
        root = Path(directory)
        key = private_tls_key()
        (root / "key.pem").write_bytes(key)
        trust = root / "cert.pem"
        trust.write_bytes(certificate("localhost", "127.0.0.1", key))
        wrong = root / "wrong.pem"
        wrong.write_bytes(certificate("localhost", "127.0.0.1", private_tls_key()))
        context = ssl.create_default_context(cafile=str(trust))

        def upstream(label, tls=False):
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    body = json.dumps({"upstream": label, "path": self.path}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *_args):
                    pass

            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            if tls:
                server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                server_context.load_cert_chain(trust, root / "key.pem")
                server.socket = server_context.wrap_socket(
                    server.socket, server_side=True
                )
            stack.callback(server.server_close)
            stack.callback(server.shutdown)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            return server.server_port

        core_port, web_port = upstream("core", True), upstream("web")

        def proxy(ca):
            listen = port()
            config = root / (str(listen) + ".Caddyfile")
            config.write_text(
                "{\n admin off\n persist_config off\n auto_https off\n}\nhttps://localhost:"
                + str(listen)
                + " {\n bind 127.0.0.1\n tls "
                + json.dumps(trust.as_posix())
                + " "
                + json.dumps((root / "key.pem").as_posix())
                + "\n"
                + agent_handle("https://127.0.0.1:" + str(core_port), ca)
                + " handle {\n reverse_proxy 127.0.0.1:"
                + str(web_port)
                + "\n }\n}\n",
                encoding="utf-8",
            )
            log = stack.enter_context((root / (str(listen) + ".log")).open("wb"))
            child = subprocess.Popen(
                [str(caddy), "run", "--config", str(config), "--adapter", "caddyfile"],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                env={
                    **os.environ,
                    "XDG_DATA_HOME": str(root / "data"),
                    "XDG_CONFIG_HOME": str(root / "config"),
                    "APPDATA": str(root / "appdata"),
                },
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            def stop():
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=10)

            stack.callback(stop)
            for _ in range(50):
                if child.poll() is not None:
                    raise ValueError("E_FIXTURE_CADDY_START")
                try:
                    with socket.create_connection(("127.0.0.1", listen), timeout=0.2):
                        return listen
                except OSError:
                    time.sleep(0.1)
            raise ValueError("E_FIXTURE_CADDY_READINESS")

        def request(listen, path, source=None, headers=None):
            connection = http.client.HTTPSConnection(
                "127.0.0.1",
                listen,
                context=context,
                timeout=10,
                source_address=(source, 0) if source else None,
            )
            try:
                connection.request(
                    "GET",
                    path,
                    headers={"Host": "localhost:" + str(listen), **(headers or {})},
                )
                response = connection.getresponse()
                return response.status, response.read()
            finally:
                connection.close()

        listener = proxy(trust)
        status, body = request(listener, "/v1/gateway-agent/enrollment-capabilities")
        if status != 200 or json.loads(body)["upstream"] != "core":
            raise ValueError("E_FIXTURE_AGENT_PROXY")
        for path in (
            "/",
            "/v1/auth/setup",
            "/v1/gateways/management",
            "/v1/voice-satellite/not-a-protocol",
        ):
            status, body = request(listener, path)
            if status != 200 or json.loads(body)["upstream"] != "web":
                raise ValueError("E_FIXTURE_CORE_ROUTE_EXPOSURE")
        untrusted = proxy(wrong)
        if request(untrusted, "/v1/gateway-agent/enrollment-capabilities")[0] != 502:
            raise ValueError("E_FIXTURE_UPSTREAM_TRUST_BYPASS")
        if (
            public_peer is not None
            and request(
                listener,
                "/v1/gateway-agent/enrollment-capabilities",
                public_peer,
                {"X-Forwarded-For": "127.0.0.1", "Forwarded": "for=127.0.0.1"},
            )[0]
            != 403
        ):
            raise ValueError("E_FIXTURE_PUBLIC_PEER_ACCEPTED")
        return {
            "actualCaddyProcessAndTls": True,
            "actualLoopbackAgentRoute": True,
            "ownerAndUnknownRoutesNotForwardedToCore": True,
            "wrongUpstreamCertificateRejected": True,
            "actualPublicPeerAndForgedForwardingHeadersDenied": public_peer is not None,
            "syntheticUpstreams": True,
            "actualCoreOrHouseholdDevices": False,
            "operatingSystemServiceAcceptance": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caddy", type=Path, required=True)
    parser.add_argument("--caddy-sha256", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--public-peer")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = exercise(
        args.caddy.resolve(), args.caddy_sha256, args.work.resolve(), args.public_peer
    )
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
