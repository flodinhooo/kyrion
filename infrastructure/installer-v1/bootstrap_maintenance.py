"""Explicit bounded renewal of the existing unused first-owner bootstrap window."""

from __future__ import annotations

import ctypes
import os
import re
import time

from bundle import sha256
from host import reject_links
from onboarding import CoreClient


def set_bootstrap_time(path, requested_at: int) -> None:
    reject_links(path)
    if type(requested_at) is not int or requested_at < 0:
        raise ValueError("E_BOOTSTRAP_FILETIME")
    if os.name != "nt":
        os.utime(path, (path.stat().st_atime, requested_at), follow_symlinks=False)
        return
    from ctypes import wintypes as w

    class FileTime(ctypes.Structure):
        _fields_ = [("low", w.DWORD), ("high", w.DWORD)]

    class Information(ctypes.Structure):
        _fields_ = [
            ("attributes", w.DWORD),
            ("created", FileTime),
            ("accessed", FileTime),
            ("written", FileTime),
            *[
                (name, w.DWORD)
                for name in (
                    "serial",
                    "sizeHigh",
                    "sizeLow",
                    "links",
                    "indexHigh",
                    "indexLow",
                )
            ],
        ]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [
        w.LPCWSTR,
        w.DWORD,
        w.DWORD,
        ctypes.c_void_p,
        w.DWORD,
        w.DWORD,
        w.HANDLE,
    ]
    api.CreateFileW.restype = w.HANDLE
    api.GetFileInformationByHandle.argtypes = [w.HANDLE, ctypes.POINTER(Information)]
    api.GetFileInformationByHandle.restype = w.BOOL
    api.SetFileTime.argtypes = [
        w.HANDLE,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    api.SetFileTime.restype = w.BOOL
    api.CloseHandle.argtypes = [w.HANDLE]
    api.CloseHandle.restype = w.BOOL
    handle = api.CreateFileW(str(path), 0x100, 3, None, 3, 0x200080, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError("E_BOOTSTRAP_FILETIME")
    try:
        info = Information()
        if (
            not api.GetFileInformationByHandle(handle, ctypes.byref(info))
            or info.attributes & 0x400
        ):
            raise ValueError("E_BOOTSTRAP_FILE")
        value = (requested_at + 11644473600) * 10000000
        stamp = FileTime(value & 0xFFFFFFFF, value >> 32)
        if not api.SetFileTime(handle, None, None, ctypes.byref(stamp)):
            raise OSError("E_BOOTSTRAP_FILETIME")
    finally:
        api.CloseHandle(handle)


def authorize_host(installation) -> None:
    if os.name == "nt":
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise ValueError("E_NATIVE_ELEVATION")
        from native_runtime import permissions

        permissions(installation.target, "verify")
    elif os.name != "posix" or os.geteuid() != 0:
        raise ValueError("E_PLATFORM")
    installation.verify_files()


def extend_bootstrap(installation) -> dict:
    authorize_host(installation)
    if installation.state.get("ownerSetup") == "authenticated":
        raise ValueError("E_BOOTSTRAP_EXPECTED_OWNER")
    client = CoreClient(installation)
    if client.request("GET", "/v1/auth/setup/status").get("setupRequired") is not True:
        raise ValueError("E_BOOTSTRAP_ALREADY_INITIALIZED")
    path = installation.target / "secrets/bootstrap.secret"
    reject_links(path)
    if (
        not path.is_file()
        or path.stat().st_size > 128
        or sha256(path) != installation.state["files"].get("secrets/bootstrap.secret")
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", path.read_text().strip())
    ):
        raise ValueError("E_BOOTSTRAP_FILE")
    now = int(time.time())
    previous = installation.state.get("bootstrapExtension")
    if previous is not None and (
        not isinstance(previous, dict)
        or set(previous) != {"requestedAt", "expiresAt", "phase"}
        or type(previous["requestedAt"]) is not int
        or type(previous["expiresAt"]) is not int
        or previous["expiresAt"] != previous["requestedAt"] + 1800
        or previous["requestedAt"] > now
        or previous["requestedAt"] < 0
        or not isinstance(previous["phase"], str)
        or previous["phase"] not in {"pending", "applied"}
    ):
        raise ValueError("E_BOOTSTRAP_EXTENSION_STATE")
    pending = (
        previous
        if previous and previous["phase"] == "pending" and previous["expiresAt"] > now
        else {"requestedAt": now, "expiresAt": now + 1800, "phase": "pending"}
    )
    installation.state["bootstrapExtension"] = pending.copy()
    try:
        installation.save()
    except BaseException:
        if previous is None:
            installation.state.pop("bootstrapExtension", None)
        else:
            installation.state["bootstrapExtension"] = previous
        raise
    # Same inode and unchanged credential bytes: Linux's read-only Compose
    # secret bind sees the new timestamp too. Core reads its age on every setup
    # verification; no new identity, credential replacement or restart needed.
    set_bootstrap_time(path, pending["requestedAt"])
    if int(path.stat().st_mtime) != pending["requestedAt"]:
        raise ValueError("E_BOOTSTRAP_FILETIME")
    installation.state["bootstrapExtension"] = {**pending, "phase": "applied"}
    installation.save()
    return {
        "expiresAt": pending["expiresAt"],
        "credentialReplaced": False,
        "accountCreated": False,
    }


def offer_bootstrap_extension(installation, messages):
    if (
        CoreClient(installation)
            .request("GET", "/v1/auth/setup/status")
            .get("setupRequired")
        is not True
    ):
        return
    path = installation.target / "secrets/bootstrap.secret"
    reject_links(path)
    if time.time() - path.stat().st_mtime < 1800:
        return
    if (
        input(messages["bootstrapExtendReview"] + " [EXTEND/CANCEL]: ").strip()
        != "EXTEND"
    ):
        raise ValueError("E_BOOTSTRAP_EXPIRED")
    extend_bootstrap(installation)
