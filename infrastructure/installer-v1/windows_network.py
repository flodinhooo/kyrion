"""Read-only Windows established TCP peer ownership, before forwarding bytes."""

from __future__ import annotations

import ctypes
import os
import socket
import struct
import time


def assert_peer(connection: socket.socket, expected_pid: int) -> None:
    # The kernel's ownership snapshot may lag a newly established loopback
    # handshake briefly. Retry without sending application data; fail closed.
    for attempt in range(6):
        try:
            _assert_peer(connection, expected_pid)
            return
        except ValueError as error:
            if str(error) != "E_NATIVE_TCP_OWNER" or attempt == 5:
                raise
            time.sleep(0.05)


def _assert_peer(connection: socket.socket, expected_pid: int) -> None:
    if os.name != "nt" or type(expected_pid) is not int or expected_pid <= 0:
        raise ValueError("E_NATIVE_TCP_PLATFORM")
    from ctypes import wintypes as w

    api = ctypes.WinDLL("iphlpapi", use_last_error=True).GetExtendedTcpTable
    api.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(w.DWORD),
        w.BOOL,
        w.ULONG,
        ctypes.c_int,
        w.ULONG,
    ]
    api.restype = w.DWORD
    size = w.DWORD()
    code = api(None, ctypes.byref(size), False, socket.AF_INET, 5, 0)
    for _ in range(4):
        if code != 122 or not 4 <= size.value <= 16 * 1024**2:
            raise ValueError("E_NATIVE_TCP_TABLE")
        table = ctypes.create_string_buffer(size.value)
        code = api(table, ctypes.byref(size), False, socket.AF_INET, 5, 0)
        if code == 0:
            break
    else:
        raise ValueError("E_NATIVE_TCP_TABLE")
    raw = table.raw[: size.value]
    count = struct.unpack_from("<I", raw)[0]
    if count > (len(raw) - 4) // 24:
        raise ValueError("E_NATIVE_TCP_TABLE")
    local = connection.getsockname()
    remote = connection.getpeername()
    for offset in range(4, 4 + count * 24, 24):
        state, address, port, peer, peer_port, pid = struct.unpack_from(
            "<6I", raw, offset
        )
        if (
            state == 5
            and socket.inet_ntoa(struct.pack("<I", address)) == remote[0]
            and socket.ntohs(port & 65535) == remote[1]
            and socket.inet_ntoa(struct.pack("<I", peer)) == local[0]
            and socket.ntohs(peer_port & 65535) == local[1]
            and pid == expected_pid
        ):
            return
    raise ValueError("E_NATIVE_TCP_OWNER")
