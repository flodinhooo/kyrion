import http.server
import socket
import ssl
import threading
import urllib.error
import urllib.request

import pytest

from kyrion_voice_satellite.http_transport import (
    CoreHttpsConnection,
    connect_core,
    open_core_url,
)


class FakeSocket:
    def __init__(self, fail=False):
        self.fail = fail
        self.closed = False
        self.timeouts = []

    def settimeout(self, seconds):
        self.timeouts.append(seconds)

    def connect(self, _endpoint):
        if self.fail:
            raise TimeoutError("synthetic black hole")

    def close(self):
        self.closed = True


def test_ipv4_is_tried_before_blackholed_ipv6_without_changing_hostname(monkeypatch):
    candidate = FakeSocket()
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 8080, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 8080)),
        ],
    )
    families = []

    def create(family, *_args):
        families.append(family)
        return candidate

    monkeypatch.setattr(socket, "socket", create)
    assert connect_core(("core.home", 8080), 180) is candidate
    assert families == [socket.AF_INET]
    assert candidate.timeouts == [2, 180]


def test_ipv6_only_hosts_remain_supported(monkeypatch):
    candidate = FakeSocket()
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 8080, 0, 0)),
        ],
    )
    monkeypatch.setattr(socket, "socket", lambda *_args: candidate)
    assert connect_core(("core.home", 8080), 90) is candidate


def test_connect_deadline_closes_failed_sockets_without_using_read_timeout(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: (
            [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 8080)),
            ]
            * 8
        ),
    )
    moments = iter([0, 0, 2.1, 4.2, 5.1])
    monkeypatch.setattr("time.monotonic", lambda: next(moments))
    created = []

    def create(*_args):
        candidate = FakeSocket(fail=True)
        created.append(candidate)
        return candidate

    monkeypatch.setattr(socket, "socket", create)
    with pytest.raises(TimeoutError, match="CORE_CONNECT_FAILED"):
        connect_core(("core.home", 8080), 180)
    assert len(created) == 3
    assert all(item.closed and item.timeouts[0] <= 2 for item in created)


def test_tls_still_requires_valid_certificate_and_hostname():
    connection = CoreHttpsConnection("core.home", timeout=90)
    assert connection._context.check_hostname
    assert connection._context.verify_mode == ssl.CERT_REQUIRED


def test_http_failure_is_not_retried_and_request_host_and_auth_are_preserved(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append((self.headers["Host"], self.headers["Authorization"]))
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://localhost:{server.server_port}/turn",
            data=b"synthetic",
            headers={"Authorization": "Bearer synthetic"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError):
            open_core_url(request, timeout=5)
        assert received == [(f"localhost:{server.server_port}", "Bearer synthetic")]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
