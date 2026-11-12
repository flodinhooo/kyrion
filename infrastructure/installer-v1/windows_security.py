"""Native virtual-account identity and actual runtime access-boundary checks."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path


def assert_identity(service_name: str) -> None:
    if os.name != "nt":
        raise ValueError("E_NATIVE_IDENTITY_PLATFORM")
    from ctypes import wintypes as w

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api.LookupAccountNameW.argtypes = [
        w.LPCWSTR,
        w.LPCWSTR,
        ctypes.c_void_p,
        ctypes.POINTER(w.DWORD),
        w.LPWSTR,
        ctypes.POINTER(w.DWORD),
        ctypes.POINTER(w.DWORD),
    ]
    api.LookupAccountNameW.restype = w.BOOL
    api.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    api.OpenProcessToken.restype = w.BOOL
    api.GetTokenInformation.argtypes = [
        w.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        w.DWORD,
        ctypes.POINTER(w.DWORD),
    ]
    api.GetTokenInformation.restype = w.BOOL
    api.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    api.EqualSid.restype = w.BOOL
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    size = w.DWORD()
    domain_size = w.DWORD()
    kind = w.DWORD()
    account = "NT SERVICE\\" + service_name
    api.LookupAccountNameW(
        None,
        account,
        None,
        ctypes.byref(size),
        None,
        ctypes.byref(domain_size),
        ctypes.byref(kind),
    )
    if not 0 < size.value <= 4096 or domain_size.value > 4096:
        raise ValueError("E_NATIVE_IDENTITY")
    expected = ctypes.create_string_buffer(size.value)
    domain = ctypes.create_unicode_buffer(max(1, domain_size.value))
    if not api.LookupAccountNameW(
        None,
        account,
        expected,
        ctypes.byref(size),
        domain,
        ctypes.byref(domain_size),
        ctypes.byref(kind),
    ):
        raise ValueError("E_NATIVE_IDENTITY")
    token = w.HANDLE()
    if not api.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ValueError("E_NATIVE_IDENTITY")
    try:
        needed = w.DWORD()
        api.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if not 0 < needed.value <= 65536:
            raise ValueError("E_NATIVE_IDENTITY")
        value = ctypes.create_string_buffer(needed.value)
        if not api.GetTokenInformation(
            token, 1, value, len(value), ctypes.byref(needed)
        ):
            raise ValueError("E_NATIVE_IDENTITY")
        actual = ctypes.cast(value, ctypes.POINTER(ctypes.c_void_p)).contents.value
        if not api.EqualSid(actual, expected):
            raise ValueError("E_NATIVE_IDENTITY")
    finally:
        kernel.CloseHandle(token)


def check_access(root: Path, role: str, executable: Path) -> None:
    def readable(path):
        try:
            with path.open("rb") as stream:
                stream.read(1)
            return True
        except PermissionError:
            return False

    if role not in {"core", "web", "caddy", "postgres-init"}:
        raise ValueError("E_NATIVE_ROLE")
    for name in (
        "bootstrap.secret",
        "credential.key",
        "audit-integrity.key",
        "postgres-password",
        "core-tls.key",
    ):
        expected = (
            role == "core" or role == "postgres-init" and name == "postgres-password"
        )
        if readable(root / "secrets" / name) != expected:
            raise ValueError("E_NATIVE_SECRET_BOUNDARY")
    if readable(root / "data/tls/key.pem") != (role == "caddy"):
        raise ValueError("E_NATIVE_SECRET_BOUNDARY")
    if readable(root / "data/web-tls/key.pem") != (role == "web"):
        raise ValueError("E_NATIVE_SECRET_BOUNDARY")
    for path in (root / "native-runtime.json", executable):
        try:
            with path.open("r+b"):
                pass
        except PermissionError:
            continue
        raise ValueError("E_NATIVE_RUNTIME_WRITABLE")


def create_private_directory(target: Path) -> None:
    """CreateDirectoryW atomically applies its DACL and refuses existing targets."""
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    from ctypes import wintypes as w

    class Attributes(ctypes.Structure):
        _fields_ = [
            ("length", w.DWORD),
            ("descriptor", ctypes.c_void_p),
            ("inherit", w.BOOL),
        ]

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        w.LPCWSTR,
        w.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(w.DWORD),
    ]
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.POINTER(Attributes)]
    kernel.CreateDirectoryW.restype = w.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    descriptor = ctypes.c_void_p()
    if not api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        "O:BAG:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)", 1, ctypes.byref(descriptor), None
    ):
        raise ValueError("E_NATIVE_DIRECTORY_DESCRIPTOR")
    try:
        attributes = Attributes(ctypes.sizeof(Attributes), descriptor, False)
        if not kernel.CreateDirectoryW(str(target), ctypes.byref(attributes)):
            if ctypes.get_last_error() == 183:
                raise ValueError("E_NATIVE_EXISTING")
            raise OSError("E_NATIVE_CREATE")
    finally:
        kernel.LocalFree(descriptor)
