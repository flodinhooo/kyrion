"""Native local-machine binding of a public installer transaction marker."""

from __future__ import annotations

import base64
import ctypes
import hmac
import os
import uuid


def marker(identifier: str) -> bytes:
    if not isinstance(identifier, str) or str(uuid.UUID(identifier)) != identifier:
        raise ValueError("E_AGENT_INGRESS_JOURNAL")
    return b"kyrion-agent-ingress-machine-v1\x00" + identifier.encode("ascii")


def crypt(raw: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 8192:
        raise ValueError("E_AGENT_INGRESS_HOST_CHANGED")
    from ctypes import wintypes as w

    class Blob(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("data", ctypes.c_void_p)]

    api = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    operation = api.CryptProtectData if protect else api.CryptUnprotectData
    operation.argtypes = [
        ctypes.POINTER(Blob),
        w.LPCWSTR if protect else ctypes.c_void_p,
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        w.DWORD,
        ctypes.POINTER(Blob),
    ]
    operation.restype = w.BOOL
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.c_void_p))
    output = Blob()
    try:
        # UI is forbidden. Local-machine protection permits the installed
        # virtual service identities to verify the same public marker.
        if not operation(
            ctypes.byref(source),
            "Kyrion ingress host binding" if protect else None,
            None,
            None,
            None,
            0x1 | (0x4 if protect else 0),
            ctypes.byref(output),
        ) or not (output.data and 0 < output.size <= 8192):
            raise ValueError("E_AGENT_INGRESS_HOST_CHANGED")
        return ctypes.string_at(output.data, output.size)
    finally:
        if output.data:
            kernel.LocalFree(output.data)


def protect_marker(identifier: str) -> str:
    return base64.b64encode(crypt(marker(identifier), protect=True)).decode("ascii")


def verify_marker(identifier: str, value: str) -> None:
    if not isinstance(value, str) or not 0 < len(value) <= 12000:
        raise ValueError("E_AGENT_INGRESS_HOST_CHANGED")
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError:
        raise ValueError("E_AGENT_INGRESS_HOST_CHANGED") from None
    if base64.b64encode(raw).decode("ascii") != value or not hmac.compare_digest(
        crypt(raw, protect=False), marker(identifier)
    ):
        raise ValueError("E_AGENT_INGRESS_HOST_CHANGED")
