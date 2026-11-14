"""Actual adapter/VRAM observations, never inference acceleration promises."""

from __future__ import annotations

import csv
import ctypes
import io
import os
import re
import uuid
from pathlib import Path

MIB = 1024**2
MAX_MEMORY = 16 * 1024**4


def memory_mib(value: str) -> int | None:
    value = value.strip()
    if not re.fullmatch(r"[0-9]{1,10}", value):
        return None
    parsed = int(value) * MIB
    return parsed if parsed <= MAX_MEMORY else None


def nvidia_rows(raw: str | None) -> list[dict] | None:
    if raw is None or len(raw) > 65536:
        return None
    try:
        rows = list(csv.reader(io.StringIO(raw), skipinitialspace=True, strict=True))
        if not 1 <= len(rows) <= 32:
            return None
        result, identifiers = [], set()
        for row in rows:
            if len(row) != 5:
                return None
            identifier, name, total, free, version = (part.strip() for part in row)
            if (
                not re.fullmatch(
                    r"GPU-[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}",
                    identifier,
                )
                or identifier.lower() in identifiers
                or not 1 <= len(name) <= 200
                or not name.isprintable()
            ):
                return None
            identifiers.add(identifier.lower())
            total_bytes, free_bytes = memory_mib(total), memory_mib(free)
            if (
                total_bytes is not None
                and free_bytes is not None
                and free_bytes > total_bytes
            ):
                free_bytes = None
            result.append(
                {
                    "source": "nvidia-smi",
                    "id": identifier,
                    "vendor": "nvidia",
                    "name": name,
                    "dedicatedVramBytes": total_bytes,
                    "freeVramBytes": free_bytes,
                    "driverVersion": version
                    if re.fullmatch(r"[0-9]{1,5}(?:\.[0-9]{1,5}){1,3}", version)
                    else None,
                    "usableAcceleration": None,
                }
            )
        return result
    except (csv.Error, ValueError, TypeError):
        return None


def bounded_text(path: Path, limit=4096) -> str:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("E_HARDWARE_OBSERVATION")
    return raw.decode("utf-8").strip()


def linux_adapters(root: Path = Path("/sys/class/drm")) -> list[dict] | None:
    result, seen = [], set()
    try:
        if not root.is_dir():
            return None
        entries = list(root.iterdir())
        if len(entries) > 256:
            return None
        for item in sorted(entries):
            if not re.fullmatch(r"card[0-9]{1,3}", item.name):
                continue
            if (
                not (item / "device/vendor").is_file()
                or not (item / "device/device").is_file()
            ):
                result.append(
                    {
                        "source": "linux-drm",
                        "sessionId": item.name,
                        "vendor": None,
                        "deviceId": None,
                        "dedicatedVramBytes": None,
                        "freeVramBytes": None,
                        "sharedMemoryLimitBytes": None,
                        "usableAcceleration": None,
                    }
                )
                continue
            device = (item / "device").resolve(strict=True)
            if device in seen:
                continue
            seen.add(device)
            vendor = bounded_text(device / "vendor")
            identifier = bounded_text(device / "device")
            if not all(
                re.fullmatch(r"0x[0-9a-fA-F]{4}", value)
                for value in (vendor, identifier)
            ):
                raise ValueError("E_HARDWARE_OBSERVATION")
            memory = None
            path = device / "mem_info_vram_total"
            if path.is_file():
                value = bounded_text(path, 64)
                if re.fullmatch(r"[0-9]{1,15}", value) and int(value) <= MAX_MEMORY:
                    memory = int(value)
            result.append(
                {
                    "source": "linux-drm",
                    "sessionId": item.name,
                    "vendor": {
                        "0x10de": "nvidia",
                        "0x1002": "amd",
                        "0x8086": "intel",
                    }.get(vendor.lower(), "other"),
                    "vendorId": vendor.lower(),
                    "deviceId": identifier.lower(),
                    "dedicatedVramBytes": memory,
                    "freeVramBytes": None,
                    "sharedMemoryLimitBytes": None,
                    "usableAcceleration": None,
                }
            )
        return result
    except (OSError, ValueError, UnicodeError):
        return None


def windows_adapters() -> list[dict] | None:
    """DXGI factory/adapter vtables, read-only; every COM reference is released."""
    from windows_system import system_directory

    class Guid(ctypes.Structure):
        _fields_ = [
            ("data1", ctypes.c_uint32),
            ("data2", ctypes.c_uint16),
            ("data3", ctypes.c_uint16),
            ("data4", ctypes.c_ubyte * 8),
        ]

    class Description(ctypes.Structure):
        _fields_ = [
            ("name", ctypes.c_wchar * 128),
            ("vendor", ctypes.c_uint32),
            ("device", ctypes.c_uint32),
            ("subsystem", ctypes.c_uint32),
            ("revision", ctypes.c_uint32),
            ("dedicated", ctypes.c_size_t),
            ("system", ctypes.c_size_t),
            ("shared", ctypes.c_size_t),
            ("luidLow", ctypes.c_uint32),
            ("luidHigh", ctypes.c_int32),
            ("flags", ctypes.c_uint32),
        ]

    def method(pointer, index, result, *arguments):
        table = ctypes.cast(
            pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *arguments)(table[index])

    def release(pointer):
        if pointer.value:
            method(pointer, 2, ctypes.c_uint32)(pointer)

    factory = ctypes.c_void_p()
    factory_owned = False
    try:
        library = ctypes.WinDLL(
            str(system_directory() / "dxgi.dll"), use_last_error=True
        )
        create = library.CreateDXGIFactory1
        create.argtypes = [ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p)]
        create.restype = ctypes.c_int32
        iid = Guid.from_buffer_copy(
            uuid.UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le
        )
        if create(ctypes.byref(iid), ctypes.byref(factory)) != 0 or not factory.value:
            return None
        factory_owned = True
        enumerate_adapter = method(
            factory,
            12,
            ctypes.c_int32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        )
        result = []
        for index in range(32):
            adapter = ctypes.c_void_p()
            code = enumerate_adapter(factory, index, ctypes.byref(adapter))
            if code & 0xFFFFFFFF == 0x887A0002:
                return result
            if code != 0 or not adapter.value:
                return None
            try:
                description = Description()
                if (
                    method(adapter, 10, ctypes.c_int32, ctypes.POINTER(Description))(
                        adapter, ctypes.byref(description)
                    )
                    != 0
                ):
                    return None
                if (
                    description.dedicated > MAX_MEMORY
                    or description.shared > MAX_MEMORY
                ):
                    return None
                result.append(
                    {
                        "source": "windows-dxgi",
                        "sessionId": f"{description.luidHigh & 0xFFFFFFFF:08x}{description.luidLow:08x}",
                        "vendor": {
                            0x10DE: "nvidia",
                            0x1002: "amd",
                            0x8086: "intel",
                        }.get(description.vendor, "other"),
                        "name": description.name
                        if description.name.isprintable()
                        else None,
                        "vendorId": f"0x{description.vendor:04x}",
                        "deviceId": f"0x{description.device:04x}",
                        "softwareAdapter": bool(description.flags & 2),
                        "dedicatedVramBytes": int(description.dedicated),
                        "sharedMemoryLimitBytes": int(description.shared),
                        "freeVramBytes": None,
                        "usableAcceleration": None,
                    }
                )
            finally:
                release(adapter)
        return None  # Truncated enumeration is not a complete adapter inventory.
    except (OSError, ValueError, ctypes.ArgumentError):
        return None
    finally:
        if factory_owned:
            release(factory)


def observe(query) -> tuple[dict, list[str] | None]:
    raw = query(
        [
            "nvidia-smi",
            "--query-gpu=uuid,name,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    return {
        "adapters": windows_adapters() if os.name == "nt" else linux_adapters(),
        "nvidia": nvidia_rows(raw),
        "usableAcceleration": None,
        "runtimeProbePerformed": False,
        "memoryViewsOverlap": True,
    }, raw.splitlines()[:32] if raw else None


def cpu_description(fallback: str | None) -> str | None:
    try:
        if os.name == "nt":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value, kind = winreg.QueryValueEx(key, "ProcessorNameString")
            if kind != winreg.REG_SZ:
                return fallback
        else:
            with Path("/proc/cpuinfo").open("rb") as stream:
                prefix = stream.read(65536).decode("utf-8")
            values = [
                line.split(":", 1)[1].strip()
                for line in prefix.splitlines()
                if line.split(":", 1)[0].strip() == "model name" and ":" in line
            ]
            value = values[0] if values else fallback
        return (
            value.strip()
            if isinstance(value, str)
            and 1 <= len(value.strip()) <= 200
            and value.strip().isprintable()
            else fallback
        )
    except (OSError, UnicodeError, ValueError):
        return fallback
