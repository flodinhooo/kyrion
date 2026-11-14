"""OS-owned Windows paths and a minimal child environment, never caller aliases."""

from __future__ import annotations

import ctypes
import os
import uuid
from pathlib import Path


def _directory(function: str) -> Path:
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    from ctypes import wintypes as w

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    call = getattr(kernel, function)
    call.argtypes = [w.LPWSTR, w.UINT]
    call.restype = w.UINT
    value = ctypes.create_unicode_buffer(32768)
    length = call(value, len(value))
    if not 0 < length < len(value):
        raise OSError("E_NATIVE_SYSTEM_DIRECTORY")
    return Path(value.value)


def system_directory() -> Path:
    return _directory("GetSystemDirectoryW")


def program_files_directory() -> Path:
    """Read the OS known folder, never a caller ProgramFiles environment alias."""
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    from ctypes import wintypes as w

    shell = ctypes.WinDLL(str(system_directory() / "shell32.dll"), use_last_error=True)
    allocator = ctypes.WinDLL(
        str(system_directory() / "ole32.dll"), use_last_error=True
    )
    lookup = shell.SHGetKnownFolderPath
    lookup.argtypes = [
        ctypes.c_void_p,
        w.DWORD,
        w.HANDLE,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    lookup.restype = ctypes.c_int32
    allocator.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    allocator.CoTaskMemFree.restype = None
    identifier = (ctypes.c_ubyte * 16).from_buffer_copy(
        uuid.UUID("905e63b6-c1bf-494e-b29c-65b732d3d21a").bytes_le
    )
    result = ctypes.c_void_p()
    try:
        if (
            lookup(ctypes.byref(identifier), 0, None, ctypes.byref(result)) != 0
            or not result.value
        ):
            raise ValueError("E_NATIVE_DATA_DIRECTORY")
        directory = Path(ctypes.wstring_at(result))
        if (
            not directory.is_absolute()
            or len(directory.drive) != 2
            or directory.drive[1] != ":"
        ):
            raise ValueError("E_NATIVE_DATA_DIRECTORY")
        return directory
    finally:
        if result.value:
            allocator.CoTaskMemFree(result)


def base_environment() -> dict[str, str]:
    # POSIX is used only for pure plan tests, never Windows process execution.
    root = _directory("GetWindowsDirectoryW") if os.name == "nt" else Path("C:/Windows")
    system = system_directory() if os.name == "nt" else root / "System32"
    return {
        "SystemRoot": str(root),
        "WINDIR": str(root),
        "SystemDrive": root.drive or "C:",
        "COMSPEC": str(system / "cmd.exe"),
        "PSModulePath": str(system / "WindowsPowerShell/v1.0/Modules"),
        "PATH": str(system),
        "TEMP": str(root / "Temp"),
        "TMP": str(root / "Temp"),
    }


def native_architecture() -> str | None:
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetNativeSystemInfo.argtypes = [ctypes.c_void_p]
    kernel.GetNativeSystemInfo.restype = None
    # SYSTEM_INFO is 48 bytes on the supported x64 ABI; an oversized aligned
    # buffer also permits a read-only native-architecture probe under emulation.
    value = (ctypes.c_uint64 * 8)()
    kernel.GetNativeSystemInfo(ctypes.byref(value))
    architecture = ctypes.cast(value, ctypes.POINTER(ctypes.c_uint16)).contents.value
    return {9: "amd64", 12: "arm64", 0: "x86"}.get(architecture)
