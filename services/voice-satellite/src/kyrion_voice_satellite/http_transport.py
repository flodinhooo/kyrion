"""Bounded TCP address selection, before sending any authenticated request bytes."""

from __future__ import annotations

import http.client
import socket
import time
import urllib.request


def connect_core(address, timeout, source_address=None):
    # Core's guarded Windows listener is IPv4. Keep the configured DNS hostname
    # for HTTP/TLS and allow IPv6-only installations to fall back before any I/O.
    candidates = socket.getaddrinfo(*address, type=socket.SOCK_STREAM)
    candidates.sort(key=lambda item: item[0] != socket.AF_INET)
    deadline = time.monotonic() + min(float(timeout), 5.0)
    for family, kind, protocol, _, endpoint in candidates[:8]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        connection = socket.socket(family, kind, protocol)
        try:
            connection.settimeout(min(2.0, remaining))
            if source_address:
                connection.bind(source_address)
            connection.connect(endpoint)
            connection.settimeout(timeout)  # Existing read/turn deadline.
            return connection
        except OSError:
            connection.close()
    raise TimeoutError("CORE_CONNECT_FAILED")


class CoreHttpConnection(http.client.HTTPConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = connect_core


class CoreHttpsConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = connect_core


class CoreHttpHandler(urllib.request.HTTPHandler):
    def http_open(self, request):
        return self.do_open(CoreHttpConnection, request)


class CoreHttpsHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(CoreHttpsConnection, request, context=self._context)


def open_core_url(request: urllib.request.Request, *, timeout: float):
    # No HTTP retry: a failure after sending bytes may have created a session or
    # executed a turn. Address fallback occurs only inside connect_core.
    return urllib.request.build_opener(CoreHttpHandler(), CoreHttpsHandler()).open(
        request,
        timeout=timeout,
    )
