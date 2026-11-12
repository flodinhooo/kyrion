"""Fail-closed reconnect policy; OS ownership acceptance lives separately."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_network import verified_connection


class Reconnect(unittest.TestCase):
    def test_rejected_socket_closed_before_new_connection(self):
        first, second = Mock(), Mock()
        child = SimpleNamespace(pid=123, poll=lambda: None)

        def connect(*args, **kwargs):
            if connect.calls:
                first.close.assert_called_once()
            connect.calls += 1
            return (first, second)[connect.calls - 1]

        connect.calls = 0
        with (
            patch("windows_network.socket.create_connection", side_effect=connect),
            patch(
                "windows_network.assert_peer",
                side_effect=[ValueError("E_NATIVE_TCP_OWNER"), None],
            ),
            verified_connection(12345, child) as connection,
        ):
            self.assertIs(connection, second)
            first.sendall.assert_not_called()
            second.sendall.assert_not_called()
        second.close.assert_called_once()

    def test_bounded_failure_closes_every_socket_without_bytes(self):
        sockets = [Mock() for _ in range(4)]
        with (
            patch("windows_network.socket.create_connection", side_effect=sockets),
            patch(
                "windows_network.assert_peer",
                side_effect=ValueError("E_NATIVE_TCP_OWNER"),
            ),
            self.assertRaisesRegex(ValueError, "E_NATIVE_TCP_OWNER"),
            verified_connection(12345, SimpleNamespace(pid=123, poll=lambda: None)),
        ):
            self.fail("unverified socket yielded")
        for connection in sockets:
            connection.close.assert_called_once()
            connection.sendall.assert_not_called()

    def test_exit_after_verification_never_yields(self):
        connection = Mock()
        child = SimpleNamespace(pid=123, poll=Mock(side_effect=[None, 1]))
        with (
            patch("windows_network.socket.create_connection", return_value=connection),
            patch("windows_network.assert_peer"),
            self.assertRaisesRegex(ValueError, "E_NATIVE_CHILD_EXIT"),
            verified_connection(12345, child),
        ):
            self.fail("exited child yielded")
        connection.close.assert_called_once()

    def test_invalid_table_is_not_retried(self):
        connection = Mock()
        with (
            patch(
                "windows_network.socket.create_connection", return_value=connection
            ) as connect,
            patch(
                "windows_network.assert_peer",
                side_effect=ValueError("E_NATIVE_TCP_TABLE"),
            ),
            self.assertRaisesRegex(ValueError, "E_NATIVE_TCP_TABLE"),
            verified_connection(12345, SimpleNamespace(pid=123, poll=lambda: None)),
        ):
            self.fail("invalid table yielded")
        connect.assert_called_once()
        connection.close.assert_called_once()
