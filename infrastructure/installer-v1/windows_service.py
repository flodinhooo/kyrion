"""Fixed native SCM plans and typed Win32 operations; no shell command endpoint."""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import PureWindowsPath

ROLES = ("postgres", "core", "web", "caddy")
DEPENDENCIES = {
    "postgres": (),
    "core": ("postgres",),
    "web": ("core",),
    "caddy": ("web",),
}


def service_plan(
    identifier: str, target: str, role: str, postgres_port: int = 5432
) -> dict:
    from windows_tasks import task_plan

    if type(postgres_port) is not int or not 1024 <= postgres_port <= 65535:
        raise ValueError("E_SERVICE_PORT")
    canonical = str(uuid.UUID(identifier))
    if identifier != canonical or role not in {*ROLES, "postgres-init"}:
        raise ValueError("E_SERVICE_IDENTITY")
    # Reuse the reviewed Windows target constraints, including environment aliases.
    task_plan(identifier, target, "core")
    root = PureWindowsPath(target)
    name = (
        "Kyrion-" + canonical + "-" + ("postgres" if role == "postgres-init" else role)
    )
    if role == "postgres":
        argv = [
            str(root / "payload/runtime/postgres/bin/pg_ctl.exe"),
            "runservice",
            "-N",
            name,
            "-D",
            str(root / "data/postgres"),
            "-w",
            "-o",
            "-h 127.0.0.1 -p " + str(postgres_port),
        ]
    else:
        argv = [
            str(root / "payload/runtime/installer/kyrion-service.exe"),
            "--windows-service",
            role,
            "--target",
            str(root),
        ]
    return {
        "name": name,
        "role": role,
        "root": str(root),
        "postgresPort": postgres_port,
        "account": "NT SERVICE\\" + name,
        "argv": argv,
        "dependencies": ["RPCSS"]
        if role in {"postgres", "postgres-init"}
        else ["Kyrion-" + canonical + "-" + r for r in DEPENDENCIES[role]],
        "description": "Kyrion installation " + canonical + "; role " + role,
    }


def validate_plan(plan: dict) -> None:
    try:
        identifier = plan["name"][7:43]
        expected = service_plan(
            identifier, plan["root"], plan["role"], plan["postgresPort"]
        )
    except (KeyError, ValueError, TypeError):
        raise ValueError("E_SERVICE_PLAN") from None
    if plan != expected:
        raise ValueError("E_SERVICE_PLAN")


def _multi_string(pointer) -> list[str]:
    values = []
    while pointer:
        value = ctypes.wstring_at(pointer)
        if not value:
            break
        values.append(value)
        pointer += (len(value) + 1) * ctypes.sizeof(ctypes.c_wchar)
    return values


class ServiceManager:
    """Native operations are internal; callers must first verify the owned root."""

    def __init__(self, writable: bool = False):
        if os.name != "nt":
            raise ValueError("E_SERVICE_PLATFORM")
        from ctypes import wintypes as w

        self.w = w

        class Config(ctypes.Structure):
            _fields_ = [
                ("kind", w.DWORD),
                ("start", w.DWORD),
                ("error", w.DWORD),
                ("binary", w.LPWSTR),
                ("group", w.LPWSTR),
                ("tag", w.DWORD),
                ("dependencies", ctypes.c_void_p),
                ("account", w.LPWSTR),
                ("display", w.LPWSTR),
            ]

        class Status(ctypes.Structure):
            _fields_ = [
                (name, w.DWORD)
                for name in (
                    "kind",
                    "state",
                    "accepted",
                    "error",
                    "specific",
                    "checkpoint",
                    "waitHint",
                    "pid",
                    "flags",
                )
            ]

        self.Config, self.Status = Config, Status
        self.api = ctypes.WinDLL("advapi32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        declarations = {
            "OpenSCManagerW": ([w.LPCWSTR, w.LPCWSTR, w.DWORD], w.HANDLE),
            "OpenServiceW": ([w.HANDLE, w.LPCWSTR, w.DWORD], w.HANDLE),
            "CloseServiceHandle": ([w.HANDLE], w.BOOL),
            "CreateServiceW": (
                [
                    w.HANDLE,
                    w.LPCWSTR,
                    w.LPCWSTR,
                    w.DWORD,
                    w.DWORD,
                    w.DWORD,
                    w.DWORD,
                    w.LPCWSTR,
                    w.LPCWSTR,
                    ctypes.POINTER(w.DWORD),
                    w.LPCWSTR,
                    w.LPCWSTR,
                    w.LPCWSTR,
                ],
                w.HANDLE,
            ),
            "QueryServiceConfigW": (
                [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)],
                w.BOOL,
            ),
            "QueryServiceStatusEx": (
                [
                    w.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    w.DWORD,
                    ctypes.POINTER(w.DWORD),
                ],
                w.BOOL,
            ),
            "ChangeServiceConfigW": (
                [
                    w.HANDLE,
                    w.DWORD,
                    w.DWORD,
                    w.DWORD,
                    w.LPCWSTR,
                    w.LPCWSTR,
                    ctypes.POINTER(w.DWORD),
                    w.LPCWSTR,
                    w.LPCWSTR,
                    w.LPCWSTR,
                    w.LPCWSTR,
                ],
                w.BOOL,
            ),
            "ChangeServiceConfig2W": ([w.HANDLE, w.DWORD, ctypes.c_void_p], w.BOOL),
            "StartServiceW": ([w.HANDLE, w.DWORD, ctypes.c_void_p], w.BOOL),
            "ControlService": ([w.HANDLE, w.DWORD, ctypes.c_void_p], w.BOOL),
            "DeleteService": ([w.HANDLE], w.BOOL),
            "ConvertStringSecurityDescriptorToSecurityDescriptorW": (
                [
                    w.LPCWSTR,
                    w.DWORD,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(w.DWORD),
                ],
                w.BOOL,
            ),
            "QueryServiceObjectSecurity": (
                [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)],
                w.BOOL,
            ),
            "GetSecurityDescriptorOwner": (
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(w.BOOL),
                ],
                w.BOOL,
            ),
            "GetSecurityDescriptorDacl": (
                [
                    ctypes.c_void_p,
                    ctypes.POINTER(w.BOOL),
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(w.BOOL),
                ],
                w.BOOL,
            ),
            "GetAclInformation": (
                [ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.c_int],
                w.BOOL,
            ),
            "GetAce": (
                [ctypes.c_void_p, w.DWORD, ctypes.POINTER(ctypes.c_void_p)],
                w.BOOL,
            ),
            "ConvertSidToStringSidW": (
                [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)],
                w.BOOL,
            ),
            "SetServiceObjectSecurity": ([w.HANDLE, w.DWORD, ctypes.c_void_p], w.BOOL),
        }
        for name, (parameters, result) in declarations.items():
            call = getattr(self.api, name)
            call.argtypes = parameters
            call.restype = result
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel.LocalFree.restype = ctypes.c_void_p
        self.manager = self.api.OpenSCManagerW(None, None, 3 if writable else 1)
        if not self.manager:
            raise OSError("E_SERVICE_MANAGER_ACCESS")
        self.writable = writable

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.api.CloseServiceHandle(self.manager)

    @contextmanager
    def opened(self, name, mutate=False):
        access = 0xF01FF if mutate else 0x20005
        handle = self.api.OpenServiceW(self.manager, name, access)
        if not handle:
            if ctypes.get_last_error() == 1060:
                yield None
                return
            raise OSError("E_SERVICE_OPEN")
        try:
            yield handle
        finally:
            self.api.CloseServiceHandle(handle)

    def query(self, handle) -> dict:
        needed = self.w.DWORD()
        self.api.QueryServiceConfigW(handle, None, 0, ctypes.byref(needed))
        if not 0 < needed.value <= 65536:
            raise OSError("E_SERVICE_CONFIG_SIZE")
        buffer = ctypes.create_string_buffer(needed.value)
        if not self.api.QueryServiceConfigW(
            handle, buffer, len(buffer), ctypes.byref(needed)
        ):
            raise OSError("E_SERVICE_QUERY")
        config = ctypes.cast(buffer, ctypes.POINTER(self.Config)).contents
        status = self.Status()
        if not self.api.QueryServiceStatusEx(
            handle, 0, ctypes.byref(status), ctypes.sizeof(status), ctypes.byref(needed)
        ):
            raise OSError("E_SERVICE_STATUS")
        return {
            "kind": config.kind,
            "start": config.start,
            "binary": config.binary,
            "account": config.account,
            "dependencies": _multi_string(config.dependencies),
            "state": status.state,
            "pid": status.pid,
            "error": status.error,
            "specificError": status.specific,
        }

    def assert_owned(self, handle, plan, security=True):
        validate_plan(plan)
        value = self.query(handle)
        if (
            value["kind"] != 16
            or value["start"] not in {2, 3, 4}
            or value["account"].casefold() != plan["account"].casefold()
            or value["dependencies"] != plan["dependencies"]
            or windows_argv(value["binary"]) != plan["argv"]
        ):
            raise ValueError("E_SERVICE_FOREIGN")
        if security:
            self.assert_security(handle)
        return value

    def assert_security(self, handle):
        w = self.w
        needed = w.DWORD()
        self.api.QueryServiceObjectSecurity(handle, 5, None, 0, ctypes.byref(needed))
        if not 0 < needed.value <= 65536:
            raise ValueError("E_SERVICE_SECURITY")
        descriptor = ctypes.create_string_buffer(needed.value)
        if not self.api.QueryServiceObjectSecurity(
            handle, 5, descriptor, len(descriptor), ctypes.byref(needed)
        ):
            raise ValueError("E_SERVICE_SECURITY")
        owner = ctypes.c_void_p()
        defaulted = w.BOOL()

        def sid_value(pointer):
            text = w.LPWSTR()
            if not self.api.ConvertSidToStringSidW(pointer, ctypes.byref(text)):
                raise ValueError("E_SERVICE_SECURITY")
            try:
                return text.value
            finally:
                self.kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))

        if not self.api.GetSecurityDescriptorOwner(
            descriptor, ctypes.byref(owner), ctypes.byref(defaulted)
        ) or sid_value(owner) not in {"S-1-5-18", "S-1-5-32-544"}:
            raise ValueError("E_SERVICE_SECURITY")
        present = w.BOOL()
        acl = ctypes.c_void_p()
        if (
            not self.api.GetSecurityDescriptorDacl(
                descriptor,
                ctypes.byref(present),
                ctypes.byref(acl),
                ctypes.byref(defaulted),
            )
            or not present
            or not acl
        ):
            raise ValueError("E_SERVICE_SECURITY")

        class AclSize(ctypes.Structure):
            _fields_ = [("count", w.DWORD), ("used", w.DWORD), ("free", w.DWORD)]

        size = AclSize()
        if (
            not self.api.GetAclInformation(
                acl, ctypes.byref(size), ctypes.sizeof(size), 2
            )
            or size.count != 2
        ):
            raise ValueError("E_SERVICE_SECURITY")
        identities = set()
        for index in range(2):
            ace = ctypes.c_void_p()
            if not self.api.GetAce(acl, index, ctypes.byref(ace)):
                raise ValueError("E_SERVICE_SECURITY")
            header = (ctypes.c_ubyte * 4).from_address(ace.value)
            mask = w.DWORD.from_address(ace.value + 4).value
            if (
                header[0] != 0
                or header[1] != 0
                or not (mask & 0x10000000 or mask & 0xF01FF == 0xF01FF)
            ):
                raise ValueError("E_SERVICE_SECURITY")
            identities.add(sid_value(ace.value + 8))
        if identities != {"S-1-5-18", "S-1-5-32-544"}:
            raise ValueError("E_SERVICE_SECURITY")

    def create(self, plan):
        validate_plan(plan)
        if not self.writable or plan["role"] == "postgres":
            raise ValueError("E_SERVICE_CREATE")
        dependencies = "\x00".join(plan["dependencies"]) + "\x00\x00"
        handle = self.api.CreateServiceW(
            self.manager,
            plan["name"],
            plan["name"],
            0xF01FF,
            16,
            4,
            1,
            subprocess.list2cmdline(plan["argv"]),
            None,
            None,
            dependencies,
            plan["account"],
            None,
        )
        if not handle:
            raise OSError("E_SERVICE_CREATE")
        try:
            self.configure(handle, plan)
            self.assert_owned(handle, plan)
        finally:
            self.api.CloseServiceHandle(handle)

    def configure(self, handle, plan):
        self.assert_owned(handle, plan, security=False)
        w = self.w

        class Action(ctypes.Structure):
            _fields_ = [("kind", w.DWORD), ("delay", w.DWORD)]

        class Recovery(ctypes.Structure):
            _fields_ = [
                ("reset", w.DWORD),
                ("reboot", w.LPWSTR),
                ("command", w.LPWSTR),
                ("count", w.DWORD),
                ("actions", ctypes.POINTER(Action)),
            ]

        class Description(ctypes.Structure):
            _fields_ = [("text", w.LPWSTR)]

        actions = (Action * 4)(
            Action(1, 10000), Action(1, 30000), Action(1, 60000), Action(0, 0)
        )
        if plan["role"] == "postgres-init":
            actions = (Action * 4)(*[Action(0, 0) for _ in range(4)])
        recovery = Recovery(86400, None, None, 4, actions)
        sid = w.DWORD(1)
        failure = w.BOOL(True)
        description = Description(plan["description"])
        for level, data in ((2, recovery), (5, sid), (4, failure), (1, description)):
            if not self.api.ChangeServiceConfig2W(handle, level, ctypes.byref(data)):
                raise OSError("E_SERVICE_POLICY")
        security = ctypes.c_void_p()
        if not self.api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            "O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)", 1, ctypes.byref(security), None
        ):
            raise OSError("E_SERVICE_SECURITY")
        try:
            if not self.api.SetServiceObjectSecurity(handle, 7, security):
                raise OSError("E_SERVICE_SECURITY")
        finally:
            self.kernel.LocalFree(security)

    def activate(self, handle, plan):
        self.assert_owned(handle, plan)
        if not self.api.ChangeServiceConfigW(
            handle,
            0xFFFFFFFF,
            3 if plan["role"] == "postgres-init" else 2,
            0xFFFFFFFF,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ):
            raise OSError("E_SERVICE_AUTOSTART")

    def begin(self, handle, plan):
        self.assert_owned(handle, plan)
        if (
            not self.api.StartServiceW(handle, 0, None)
            and ctypes.get_last_error() != 1056
        ):
            raise OSError("E_SERVICE_START")

    def disable(self, handle, plan):
        self.assert_owned(handle, plan)
        if not self.writable or not self.api.ChangeServiceConfigW(
            handle,
            0xFFFFFFFF,
            4,
            0xFFFFFFFF,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ):
            raise OSError("E_SERVICE_DISABLE")

    def demand(self, handle, plan):
        self.assert_owned(handle, plan)
        if not self.writable or not self.api.ChangeServiceConfigW(
            handle,
            0xFFFFFFFF,
            3,
            0xFFFFFFFF,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ):
            raise OSError("E_SERVICE_DEMAND_START")

    def start(self, handle, plan, timeout=150):
        self.assert_owned(handle, plan)
        if (
            not self.api.StartServiceW(handle, 0, None)
            and ctypes.get_last_error() != 1056
        ):
            raise OSError("E_SERVICE_START")
        self.wait(handle, 4, timeout)

    def stop(self, handle, plan, timeout=60):
        value = self.assert_owned(handle, plan)
        if value["state"] == 1:
            return
        status = self.Status()
        if (
            not self.api.ControlService(handle, 1, ctypes.byref(status))
            and ctypes.get_last_error() != 1062
        ):
            raise OSError("E_SERVICE_STOP")
        self.wait(handle, 1, timeout)

    def wait(self, handle, state, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.query(handle)
            if value["state"] == state:
                return
            if state == 4 and value["state"] == 1:
                raise OSError("E_SERVICE_FAILED")
            time.sleep(0.25)
        raise OSError("E_SERVICE_TIMEOUT")

    def wait_removed(self, name, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            handle = self.api.OpenServiceW(self.manager, name, 1)
            if not handle:
                error = ctypes.get_last_error()
                if error == 1060:
                    return
                if error != 1072:
                    raise OSError("E_SERVICE_OPEN")
            else:
                self.api.CloseServiceHandle(handle)
            time.sleep(0.1)
        raise OSError("E_SERVICE_DELETE_PENDING")

    def remove(self, handle, plan):
        self.stop(handle, plan)
        if not self.api.DeleteService(handle):
            raise OSError("E_SERVICE_REMOVE")


def windows_argv(command: str) -> list[str]:
    from ctypes import wintypes as w

    library = ctypes.WinDLL("shell32", use_last_error=True)
    library.CommandLineToArgvW.argtypes = [w.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    library.CommandLineToArgvW.restype = ctypes.POINTER(w.LPWSTR)
    count = ctypes.c_int()
    pointer = library.CommandLineToArgvW(command, ctypes.byref(count))
    if not pointer:
        raise ValueError("E_SERVICE_COMMAND")
    try:
        return [pointer[i] for i in range(count.value)]
    finally:
        kernel = ctypes.WinDLL("kernel32")
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(pointer)
