"""Bounded, read-only target observations; missing facts remain None."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path


def command(args: list[str], timeout: int = 8) -> str | None:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None


def linux_release() -> dict[str, str]:
    try:
        return dict(
            line.split("=", 1)
            for line in Path("/etc/os-release").read_text().splitlines()
            if "=" in line
        )
    except OSError:
        return {}


def ram_bytes() -> int | None:
    if os.name == "nt":

        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong)
                for name in (
                    "total",
                    "available",
                    "page",
                    "page_available",
                    "virtual",
                    "virtual_available",
                    "extended",
                )
            ]

        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        return (
            memory.total
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
            else None
        )
    try:
        return next(
            int(line.split()[1]) * 1024
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemTotal:")
        )
    except (OSError, StopIteration, ValueError):
        return None


def nearest_existing(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise ValueError("E_TARGET: symlink/junction paths are refused")


def inventory(target: Path) -> dict:
    system = platform.system()
    fields = linux_release() if system == "Linux" else {}
    machine = platform.machine().lower()
    architecture = {
        "aarch64": "arm64",
        "arm64": "arm64",
        "amd64": "amd64",
        "x86_64": "amd64",
    }.get(machine)
    os_id = fields.get("ID", "").strip('"')
    version = fields.get("VERSION_ID", "").strip('"')
    candidate = (
        system == "Linux"
        and os_id in {"debian", "raspbian"}
        and version == "13"
        and architecture is not None
    )
    ancestor = nearest_existing(target)
    try:
        free = shutil.disk_usage(ancestor).free
    except OSError:
        free = None
    gpu = command(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
    )
    # Report observed vendor values only; driver presence is not runtime acceleration.
    gpu_rows = gpu.splitlines()[:8] if gpu else None
    usb = None
    if system == "Linux":
        usb = command(["lsusb"])
    ollama = command(["ollama", "--version"])
    return {
        "system": system,
        "osId": os_id or None,
        "osVersion": version if system == "Linux" else platform.version(),
        "architecture": architecture,
        "cpu": platform.processor() or None,
        "cpuCount": os.cpu_count(),
        "ramBytes": ram_bytes(),
        "freeBytes": free,
        "gpuVendorObservation": gpu_rows,
        "usableAcceleration": None,
        "usbObservation": usb.splitlines()[:32] if usb else None,
        "hardwareOwnership": None,
        "ollamaVersion": ollama,
        "tools": {
            tool: shutil.which(tool) is not None
            for tool in ("docker", "openssl", "systemctl")
        },
        "targetExists": target.exists() or target.is_symlink(),
        "existingInstallation": (target / "install-state.json").is_file(),
        "candidateProvisioning": candidate,
        "platformAccepted": False,
        "bootMode": "requires-enabled-docker-system-service"
        if candidate
        else "unavailable",
    }


def runtime_checks(address: str, hostname: str, fresh: bool = True) -> None:
    if command(["docker", "compose", "version", "--short"]) is None:
        raise ValueError("E_COMPOSE: Docker Compose v2 is required")
    info = command(["docker", "info", "--format", "{{json .}}"])
    try:
        data = json.loads(info or "null")
        if not isinstance(data, dict) or data.get("OSType") != "linux":
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError(
            "E_DOCKER: reachable local Linux Docker Engine required"
        ) from None
    # Refuse a remote engine: probes and paths must describe the actual target.
    context = command(["docker", "context", "inspect"])
    try:
        endpoint = json.loads(context or "null")[0]["Endpoints"]["docker"]["Host"]
    except (ValueError, TypeError, IndexError, KeyError):
        raise ValueError("E_DOCKER: cannot establish runtime locality") from None
    if (
        os.environ.get("DOCKER_HOST")
        or os.environ.get("DOCKER_CONTEXT")
        or not endpoint.startswith("unix://")
    ):
        raise ValueError("E_DOCKER: remote or overridden Docker contexts are refused")
    if command(["systemctl", "is-active", "docker"]) != "active":
        raise ValueError("E_AUTOSTART: Docker system service must be active")
    if command(["systemctl", "is-enabled", "docker"]) != "enabled":
        raise ValueError(
            "E_AUTOSTART: enable Docker system startup explicitly before installation"
        )
    try:
        addresses = {
            entry[4][0] for entry in socket.getaddrinfo(hostname, 443, socket.AF_INET)
        }
        if address not in addresses:
            raise ValueError(
                "E_HOSTNAME: hostname must resolve to the chosen target address"
            )
        if fresh:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind((address, 443))
    except OSError:
        raise ValueError(
            "E_NETWORK: chosen local address or HTTPS port unavailable"
        ) from None
