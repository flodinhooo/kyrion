"""Owner-bound Windows storage for the existing prepared agent identity."""

from __future__ import annotations

import contextlib
import ctypes
import functools
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

SYSTEM = "S-1-5-18"
ADMINISTRATORS = "S-1-5-32-544"
FULL_ACCESS = 0x1F01FF
REPLACE_ANCESTOR = 0x500D0042


@dataclass(frozen=True, slots=True)
class Security:
    owner: str
    protected: bool
    aces: tuple[tuple[int, int, int, str], ...]


class Api:
    def __init__(self):
        if os.name != "nt":
            raise ValueError("E_AGENT_PLATFORM")
        from ctypes import wintypes as w

        self.w = w
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.security = ctypes.WinDLL("advapi32", use_last_error=True)

        class Attributes(ctypes.Structure):
            _fields_ = [("length", w.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", w.BOOL)]

        class Acl(ctypes.Structure):
            _fields_ = [
                ("revision", w.BYTE),
                ("reserved", w.BYTE),
                ("size", w.WORD),
                ("count", w.WORD),
                ("reserved2", w.WORD),
            ]

        self.Attributes, self.Acl = Attributes, Acl
        pointer = ctypes.c_void_p
        self.bind(self.kernel, "GetCurrentProcess", [], w.HANDLE)
        self.bind(self.kernel, "CloseHandle", [w.HANDLE], w.BOOL)
        self.bind(self.kernel, "LocalFree", [pointer], pointer)
        self.bind(self.kernel, "CreateDirectoryW", [w.LPCWSTR, ctypes.POINTER(Attributes)], w.BOOL)
        self.bind(
            self.kernel,
            "CreateFileW",
            [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.POINTER(Attributes), w.DWORD, w.DWORD, w.HANDLE],
            w.HANDLE,
        )
        self.bind(self.kernel, "MoveFileExW", [w.LPCWSTR, w.LPCWSTR, w.DWORD], w.BOOL)
        self.bind(self.kernel, "GetDriveTypeW", [w.LPCWSTR], w.UINT)
        self.bind(self.kernel, "GetSystemDirectoryW", [w.LPWSTR, w.UINT], w.UINT)
        self.bind(
            self.kernel,
            "GetVolumeInformationW",
            [w.LPCWSTR, w.LPWSTR, w.DWORD, pointer, pointer, pointer, w.LPWSTR, w.DWORD],
            w.BOOL,
        )
        self.bind(
            self.security, "OpenProcessToken", [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL
        )
        self.bind(
            self.security,
            "GetTokenInformation",
            [w.HANDLE, ctypes.c_int, pointer, w.DWORD, ctypes.POINTER(w.DWORD)],
            w.BOOL,
        )
        self.bind(
            self.security, "ConvertSidToStringSidW", [pointer, ctypes.POINTER(pointer)], w.BOOL
        )
        self.bind(
            self.security,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            [w.LPCWSTR, w.DWORD, ctypes.POINTER(pointer), pointer],
            w.BOOL,
        )
        self.bind(
            self.security,
            "GetFileSecurityW",
            [w.LPCWSTR, w.DWORD, pointer, w.DWORD, ctypes.POINTER(w.DWORD)],
            w.BOOL,
        )
        self.bind(
            self.security,
            "GetKernelObjectSecurity",
            [w.HANDLE, w.DWORD, pointer, w.DWORD, ctypes.POINTER(w.DWORD)],
            w.BOOL,
        )
        self.bind(
            self.security,
            "GetSecurityDescriptorOwner",
            [pointer, ctypes.POINTER(pointer), ctypes.POINTER(w.BOOL)],
            w.BOOL,
        )
        self.bind(
            self.security,
            "GetSecurityDescriptorDacl",
            [pointer, ctypes.POINTER(w.BOOL), ctypes.POINTER(pointer), ctypes.POINTER(w.BOOL)],
            w.BOOL,
        )
        self.bind(
            self.security,
            "GetSecurityDescriptorControl",
            [pointer, ctypes.POINTER(w.WORD), ctypes.POINTER(w.DWORD)],
            w.BOOL,
        )
        self.bind(self.security, "GetAce", [pointer, w.DWORD, ctypes.POINTER(pointer)], w.BOOL)
        self.bind(self.security, "GetLengthSid", [pointer], w.DWORD)
        self.bind(
            self.security,
            "LookupAccountNameW",
            [
                w.LPCWSTR,
                w.LPCWSTR,
                pointer,
                ctypes.POINTER(w.DWORD),
                w.LPWSTR,
                ctypes.POINTER(w.DWORD),
                ctypes.POINTER(w.DWORD),
            ],
            w.BOOL,
        )
        self.owner = self.current_sid()
        self.trusted = {self.owner, SYSTEM, ADMINISTRATORS}
        installer = self.lookup("NT SERVICE\\TrustedInstaller")
        self.ancestors = self.trusted | ({installer} if installer else set())

    @staticmethod
    def bind(library, name, arguments, result):
        operation = getattr(library, name)
        operation.argtypes, operation.restype = arguments, result

    def sid(self, value) -> str:
        text = ctypes.c_void_p()
        if not self.security.ConvertSidToStringSidW(value, ctypes.byref(text)):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        try:
            return ctypes.wstring_at(text)
        finally:
            self.kernel.LocalFree(text)

    def current_sid(self) -> str:
        token = self.w.HANDLE()
        if not self.security.OpenProcessToken(
            self.kernel.GetCurrentProcess(), 0x8, ctypes.byref(token)
        ):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        try:
            needed = self.w.DWORD()
            self.security.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
            if not 0 < needed.value <= 65536:
                raise ValueError("E_AGENT_PRIVATE_FILE")
            buffer = ctypes.create_string_buffer(needed.value)
            if not self.security.GetTokenInformation(
                token, 1, buffer, len(buffer), ctypes.byref(needed)
            ):
                raise ValueError("E_AGENT_PRIVATE_FILE")
            return self.sid(ctypes.c_void_p.from_buffer(buffer).value)
        finally:
            self.kernel.CloseHandle(token)

    def lookup(self, account: str) -> str | None:
        size, domain_size, kind = self.w.DWORD(), self.w.DWORD(), self.w.DWORD()
        self.security.LookupAccountNameW(
            None,
            account,
            None,
            ctypes.byref(size),
            None,
            ctypes.byref(domain_size),
            ctypes.byref(kind),
        )
        if not (0 < size.value <= 4096 and domain_size.value <= 1024):
            return None
        buffer = ctypes.create_string_buffer(size.value)
        domain = ctypes.create_unicode_buffer(max(1, domain_size.value))
        if not self.security.LookupAccountNameW(
            None,
            account,
            buffer,
            ctypes.byref(size),
            domain,
            ctypes.byref(domain_size),
            ctypes.byref(kind),
        ):
            return None
        return self.sid(buffer)

    def inspect(self, path: Path | None = None, *, handle=None) -> Security:
        operation = (
            self.security.GetFileSecurityW
            if handle is None
            else self.security.GetKernelObjectSecurity
        )
        target = native_path(path) if handle is None else handle
        needed = self.w.DWORD()
        operation(target, 5, None, 0, ctypes.byref(needed))
        if not 0 < needed.value <= 65536:
            raise ValueError("E_AGENT_PRIVATE_FILE")
        buffer = ctypes.create_string_buffer(needed.value)
        if not operation(target, 5, buffer, len(buffer), ctypes.byref(needed)):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        owner, dacl = ctypes.c_void_p(), ctypes.c_void_p()
        present, defaulted = self.w.BOOL(), self.w.BOOL()
        control, revision = self.w.WORD(), self.w.DWORD()
        if (
            not self.security.GetSecurityDescriptorOwner(
                buffer, ctypes.byref(owner), ctypes.byref(defaulted)
            )
            or not owner.value
            or not self.security.GetSecurityDescriptorDacl(
                buffer, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)
            )
            or not present.value
            or not dacl.value
            or not self.security.GetSecurityDescriptorControl(
                buffer, ctypes.byref(control), ctypes.byref(revision)
            )
        ):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        acl = ctypes.cast(dacl, ctypes.POINTER(self.Acl)).contents
        if acl.count > 256:
            raise ValueError("E_AGENT_PRIVATE_FILE")
        entries = []
        for index in range(acl.count):
            ace = ctypes.c_void_p()
            if not self.security.GetAce(dacl, index, ctypes.byref(ace)):
                raise ValueError("E_AGENT_PRIVATE_FILE")
            header = ctypes.string_at(ace, 8)
            size = int.from_bytes(header[2:4], "little")
            if header[0] not in {0, 1} or size < 16:
                raise ValueError("E_AGENT_PRIVATE_FILE")
            sid = ace.value + 8
            length = self.security.GetLengthSid(sid)
            if not 8 <= length <= 68 or length + 8 > size:
                raise ValueError("E_AGENT_PRIVATE_FILE")
            entries.append(
                (header[0], header[1], int.from_bytes(header[4:8], "little"), self.sid(sid))
            )
        return Security(self.sid(owner), bool(control.value & 0x1000), tuple(entries))

    @contextlib.contextmanager
    def attributes(self, *, directory: bool):
        inheritance = "OICI" if directory else ""
        sddl = (
            "O:"
            + self.owner
            + "D:P"
            + "".join("(A;" + inheritance + ";FA;;;" + sid + ")" for sid in sorted(self.trusted))
        )
        descriptor = ctypes.c_void_p()
        if not self.security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        try:
            yield self.Attributes(ctypes.sizeof(self.Attributes), descriptor, False)
        finally:
            self.kernel.LocalFree(descriptor)


@functools.lru_cache(maxsize=1)
def api() -> Api:
    return Api()


def native_path(path: Path) -> str:
    if not path.is_absolute() or not re.fullmatch(r"[A-Za-z]:", path.drive) or ".." in path.parts:
        raise ValueError("E_AGENT_PRIVATE_PATH")
    for part in path.parts[1:]:
        if (
            not part
            or part.endswith((".", " "))
            or any(character in ':<>"|?*' or ord(character) < 32 for character in part)
            or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
        ):
            raise ValueError("E_AGENT_PRIVATE_PATH")
    return "\\\\?\\" + str(path)


def reject_reparse(path: Path) -> None:
    native_path(path)
    for item in (path, *path.parents):
        try:
            if item.lstat().st_file_attributes & 0x400:
                raise ValueError("E_AGENT_PRIVATE_PATH")
        except FileNotFoundError:
            continue


def private_security(value: Security, *, inherited=False, current_owner=True) -> None:
    allowed = api().trusted
    owners = {api().owner} if current_owner else allowed
    if value.owner not in owners or (not inherited and not value.protected):
        raise ValueError("E_AGENT_PRIVATE_FILE")
    seen = set()
    for kind, flags, mask, sid in value.aces:
        if inherited and (kind == 1 or flags & 0x08):
            continue
        if (
            kind != 0
            or sid not in allowed
            or flags & 0x08
            or (not inherited and mask & FULL_ACCESS != FULL_ACCESS)
        ):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        seen.add(sid)
    if (not inherited and seen != allowed) or not seen:
        raise ValueError("E_AGENT_PRIVATE_FILE")


def ancestors(path: Path) -> None:
    reject_reparse(path)
    for parent in reversed(path.parents):
        if not parent.exists():
            continue
        security = api().inspect(parent)
        if security.owner not in api().ancestors:
            raise ValueError("E_AGENT_PRIVATE_PATH")
        if any(
            kind == 0
            and not flags & 0x08
            and sid not in api().ancestors
            and mask & REPLACE_ANCESTOR
            for kind, flags, mask, sid in security.aces
        ):
            raise ValueError("E_AGENT_PRIVATE_PATH")


def private_directory(directory: Path, *, exclusive: bool = False) -> None:
    ancestors(directory)
    filesystem = ctypes.create_unicode_buffer(32)
    if (
        api().kernel.GetDriveTypeW(directory.anchor) != 3
        or not api().kernel.GetVolumeInformationW(
            directory.anchor, None, 0, None, None, None, filesystem, len(filesystem)
        )
        or filesystem.value != "NTFS"
    ):
        raise ValueError("E_AGENT_PRIVATE_FILESYSTEM")
    if directory.exists() and exclusive:
        raise ValueError("E_AGENT_PRIVATE_PATH")
    if not directory.exists():
        if not directory.parent.exists():
            private_directory(directory.parent)
        with api().attributes(directory=True) as attributes:
            if not api().kernel.CreateDirectoryW(
                native_path(directory), ctypes.byref(attributes)
            ) and (exclusive or ctypes.get_last_error() != 183):
                raise ValueError("E_AGENT_PRIVATE_PATH")
    if not directory.is_dir():
        raise ValueError("E_AGENT_PRIVATE_PATH")
    reject_reparse(directory)
    private_security(api().inspect(directory))


def local_data() -> Path:
    """Resolve the actual local known folder, never a caller environment alias."""
    directory = ctypes.create_unicode_buffer(32768)
    length = api().kernel.GetSystemDirectoryW(directory, len(directory))
    if not 0 < length < len(directory):
        raise ValueError("E_AGENT_PRIVATE_PATH")
    shell = ctypes.WinDLL(str(Path(directory.value) / "shell32.dll"), use_last_error=True)
    allocator = ctypes.WinDLL(str(Path(directory.value) / "ole32.dll"), use_last_error=True)
    api().bind(
        shell,
        "SHGetKnownFolderPath",
        [ctypes.c_void_p, api().w.DWORD, api().w.HANDLE, ctypes.POINTER(ctypes.c_void_p)],
        ctypes.c_int32,
    )
    api().bind(allocator, "CoTaskMemFree", [ctypes.c_void_p], None)
    api().bind(allocator, "CoInitializeEx", [ctypes.c_void_p, api().w.DWORD], ctypes.c_int32)
    api().bind(allocator, "CoUninitialize", [], None)
    initialized = allocator.CoInitializeEx(None, 0)
    if initialized not in {0, 1, -2147417850}:
        raise ValueError("E_AGENT_PRIVATE_PATH")
    identifier = (ctypes.c_ubyte * 16).from_buffer_copy(
        uuid.UUID("f1b32785-6fba-4fcf-9d55-7b8e7f157091").bytes_le
    )
    result = ctypes.c_void_p()
    try:
        if (
            shell.SHGetKnownFolderPath(ctypes.byref(identifier), 0, None, ctypes.byref(result)) != 0
            or not result.value
        ):
            raise ValueError("E_AGENT_PRIVATE_PATH")
        path = Path(ctypes.wstring_at(result))
        native_path(path)
        ancestors(path / "unused")
        return path
    finally:
        if result.value:
            allocator.CoTaskMemFree(result)
        if initialized in {0, 1}:
            allocator.CoUninitialize()


@contextlib.contextmanager
def temporary_directory():
    parent = local_data()
    name = "kyrion-pairing-" + uuid.uuid4().hex
    directory = parent / name
    private_directory(directory, exclusive=True)
    try:
        yield directory
    finally:
        reject_reparse(directory)
        if directory.name != name or directory.resolve().parent != parent.resolve():
            raise ValueError("E_AGENT_PRIVATE_PATH")
        private_security(api().inspect(directory))
        entries = list(directory.iterdir())
        for path in entries:
            # Refuse unexpected directories/links instead of recursive cleanup.
            read_private(path)
        for path in entries:
            path.unlink()
        directory.rmdir()


def open_file(path: Path, *, access: int, creation: int, share=1) -> int:
    import msvcrt

    reject_reparse(path)
    with api().attributes(directory=False) as attributes:
        handle = api().kernel.CreateFileW(
            native_path(path), access, share, ctypes.byref(attributes), creation, 0x200080, None
        )
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error == 32:
            raise ValueError("E_AGENT_ENROLLMENT_BUSY")
        raise ValueError("E_AGENT_PRIVATE_FILE")
    try:
        mode = os.O_RDWR if access & 0x80000000 else os.O_WRONLY
        return msvcrt.open_osfhandle(
            handle, os.O_BINARY | (mode if access & 0x40000000 else os.O_RDONLY)
        )
    except BaseException:
        api().kernel.CloseHandle(handle)
        raise


def validate_file(descriptor: int, *, inherited=False, current_owner=True) -> None:
    import msvcrt

    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_file_attributes & 0x400
    ):
        raise ValueError("E_AGENT_PRIVATE_FILE")
    private_security(
        api().inspect(handle=msvcrt.get_osfhandle(descriptor)),
        inherited=inherited,
        current_owner=current_owner,
    )


def read_private(path: Path, maximum=65536, *, inherited=False, current_owner=True) -> bytes:
    ancestors(path)
    descriptor = open_file(path, access=0x80000000, creation=3)
    with os.fdopen(descriptor, "rb") as stream:
        validate_file(stream.fileno(), inherited=inherited, current_owner=current_owner)
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("E_AGENT_PRIVATE_FILE")
    return raw


def publish(path: Path, raw: bytes) -> None:
    private_directory(path.parent)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    created = False
    try:
        descriptor = open_file(temporary, access=0x40000000, creation=1, share=0)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if not api().kernel.MoveFileExW(native_path(temporary), native_path(path), 0x8):
            if ctypes.get_last_error() in {80, 183}:
                raise FileExistsError("E_AGENT_CONFIG_EXISTS")
            raise ValueError("E_AGENT_PRIVATE_FILE")
    finally:
        if created:
            temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def enrollment_lock(path: Path):
    private_directory(path.parent)
    descriptor = open_file(path, access=0xC0000000, creation=4, share=0)
    try:
        validate_file(descriptor)
        yield
    finally:
        os.close(descriptor)
