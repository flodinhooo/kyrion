"""Prepared nodes connect only to checked LAN/loopback sockets with verified TLS."""

from __future__ import annotations

import ipaddress
import socket
import ssl
import time
from http.client import HTTPSConnection
from urllib.request import HTTPSHandler, Request

NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    )
)


def local_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return any(address.version == network.version and address in network for network in NETWORKS)


def connect_local(host: str, port: int, timeout: float) -> socket.socket:
    deadline = time.monotonic() + timeout
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if (
        not addresses
        or len(addresses) > 16
        or any(not local_address(row[4][0]) for row in addresses)
    ):
        raise OSError("E_AGENT_LOCAL_ADDRESS_REQUIRED")
    for family, kind, protocol, _canonical, address in addresses:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        selected = socket.socket(family, kind, protocol)
        try:
            selected.settimeout(remaining)
            # Numeric sockaddr from this single checked lookup; no second DNS.
            selected.connect(address)
            if not local_address(selected.getpeername()[0]):
                raise OSError("E_AGENT_LOCAL_ADDRESS_REQUIRED")
            return selected
        except OSError:
            selected.close()
    raise OSError("E_AGENT_LOCAL_CONNECTION")


class LocalHTTPSConnection(HTTPSConnection):
    def __init__(self, host: str, *, context: ssl.SSLContext, timeout: float = 10):
        self.local_context = context
        super().__init__(host, timeout=timeout, context=context)

    def set_tunnel(
        self, host: str, port: int | None = None, headers: dict[str, str] | None = None
    ) -> None:
        raise OSError("E_AGENT_PROXY_FORBIDDEN")

    def connect(self) -> None:
        selected = connect_local(self.host, self.port, float(self.timeout))
        try:
            self.sock = self.local_context.wrap_socket(selected, server_hostname=self.host)
        except BaseException:
            selected.close()
            raise


class LocalHTTPSHandler(HTTPSHandler):
    def __init__(self, context: ssl.SSLContext):
        super().__init__(context=context)
        self.local_context = context

    def https_open(self, request: Request):
        return self.do_open(LocalHTTPSConnection, request, context=self.local_context)
