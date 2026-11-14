"""Socket boundary is injected; real TLS is exercised in test_client."""

import socket
import unittest
from unittest.mock import Mock, patch

from kyrion_gateway_agent.lan_transport import connect_local, local_address


class LocalTransport(unittest.TestCase):
    def test_only_explicit_lan_and_loopback_ranges_are_accepted(self):
        for value in (
            "127.0.0.1",
            "10.1.2.3",
            "172.16.0.1",
            "192.168.1.1",
            "::1",
            "fd12::1",
            "::ffff:192.168.1.1",
        ):
            self.assertTrue(local_address(value), value)
        for value in (
            "0.0.0.0",
            "169.254.169.254",
            "224.0.0.1",
            "255.255.255.255",
            "8.8.8.8",
            "::",
            "fe80::1",
            "2001:4860:4860::8888",
            "hostname",
        ):
            self.assertFalse(local_address(value), value)

    def test_mixed_public_dns_answers_fail_before_connecting(self):
        addresses = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        ]
        with (
            patch("socket.getaddrinfo", return_value=addresses),
            patch("socket.socket") as connect,
            self.assertRaisesRegex(OSError, "E_AGENT_LOCAL_ADDRESS_REQUIRED"),
        ):
            connect_local("fixture.local", 443, 1)
        connect.assert_not_called()

    def test_checked_numeric_address_is_connected_without_another_lookup(self):
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        selected = Mock()
        selected.getpeername.return_value = ("127.0.0.1", 443)
        with (
            patch("socket.getaddrinfo", return_value=addresses) as lookup,
            patch("socket.socket", return_value=selected),
        ):
            self.assertIs(connect_local("fixture.local", 443, 1), selected)
        lookup.assert_called_once_with("fixture.local", 443, type=socket.SOCK_STREAM)
        selected.connect.assert_called_once_with(("127.0.0.1", 443))

    def test_unexpected_public_peer_is_closed_and_refused(self):
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        selected = Mock()
        selected.getpeername.return_value = ("8.8.8.8", 443)
        with (
            patch("socket.getaddrinfo", return_value=addresses),
            patch("socket.socket", return_value=selected),
            self.assertRaisesRegex(OSError, "E_AGENT_LOCAL_CONNECTION"),
        ):
            connect_local("fixture.local", 443, 1)
        selected.close.assert_called_once()
