"""Read-only local TCP listener scope; never infer safety from connect success."""

from __future__ import annotations

import ctypes
import ipaddress
import os
import socket
import struct
import sys
from pathlib import Path

LIMIT = 4 * 1024**2


def linux_rows() -> list[tuple[str, int]]:
    rows = []
    for name, width, family in (
        ("tcp", 4, socket.AF_INET),
        ("tcp6", 16, socket.AF_INET6),
    ):
        path = Path("/proc/net") / name
        # No IPv6 stack means no IPv6 listeners, not an unreadable table.
        if name == "tcp6" and not path.exists():
            continue
        with path.open("rb") as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("E_OLLAMA_BINDING")
        for line in raw.decode("ascii").splitlines()[1:]:
            fields = line.split()
            if len(fields) < 4:
                raise ValueError("E_OLLAMA_BINDING")
            if fields[3] != "0A":
                continue
            address, port = fields[1].split(":")
            value = bytes.fromhex(address)
            if len(value) != width:
                raise ValueError("E_OLLAMA_BINDING")
            # proc emits each native-endian u32 as eight hex digits.
            value = b"".join(
                int.from_bytes(value[index : index + 4], "big").to_bytes(
                    4, sys.byteorder
                )
                for index in range(0, width, 4)
            )
            rows.append((socket.inet_ntop(family, value), int(port, 16)))
    return rows


def windows_records() -> list[tuple[str, int, int]]:
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
    rows = []
    for family, row_size, address_offset, address_size, port_offset in (
        (socket.AF_INET, 24, 4, 4, 8),
        (socket.AF_INET6, 56, 0, 16, 20),
    ):
        size = w.DWORD()
        if api(None, ctypes.byref(size), False, family, 3, 0) != 122:
            raise ValueError("E_OLLAMA_BINDING")
        for _ in range(3):
            if not 4 <= size.value <= LIMIT:
                raise ValueError("E_OLLAMA_BINDING")
            buffer = ctypes.create_string_buffer(size.value)
            result = api(buffer, ctypes.byref(size), False, family, 3, 0)
            if result != 122:
                break
        if result != 0 or not 4 <= size.value <= len(buffer):
            raise ValueError("E_OLLAMA_BINDING")
        raw = buffer.raw[: size.value]
        count = struct.unpack_from("<I", raw)[0]
        if count > 65536 or 4 + count * row_size > len(raw):
            raise ValueError("E_OLLAMA_BINDING")
        for index in range(count):
            offset = 4 + index * row_size
            address = raw[
                offset + address_offset : offset + address_offset + address_size
            ]
            port = struct.unpack_from("!H", raw, offset + port_offset)[0]
            pid = struct.unpack_from("<I", raw, offset + row_size - 4)[0]
            rows.append((socket.inet_ntop(family, address), port, pid))
    return rows


def windows_rows() -> list[tuple[str, int]]:
    return [(address, port) for address, port, _pid in windows_records()]


def loopback_bindings(port: int) -> tuple[str, ...]:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("E_OLLAMA_ENDPOINT")
    try:
        rows = windows_rows() if os.name == "nt" else linux_rows()
        addresses = sorted({address for address, found in rows if found == port})
        if not addresses or any(
            not ipaddress.ip_address(address).is_loopback for address in addresses
        ):
            raise ValueError("E_OLLAMA_BINDING")
        return tuple(addresses)
    except (OSError, ValueError, IndexError, UnicodeError, struct.error):
        raise ValueError("E_OLLAMA_BINDING") from None
