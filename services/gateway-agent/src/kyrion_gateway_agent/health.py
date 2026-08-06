from __future__ import annotations

import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any  # noqa: UP035

SERVICE_UNITS = {
    "home-assistant": "home-assistant.service",
    "matter": "matter-server.service",
    "mqtt": "mosquitto.service",
    "otbr": "otbr-agent.service",
    "voice": "kyrion-voice-satellite.service",
    "zigbee": "zigbee2mqtt.service",
}
NON_RUNTIME_FAILED_UNITS = {"NetworkManager-wait-online.service"}


def collect_health() -> dict[str, Any]:
    memory_total, memory_available = _memory()
    storage = shutil.disk_usage("/")
    return {
        "temperatureCelsius": _temperature(),
        "throttled": _throttled(),
        "memoryTotalBytes": memory_total,
        "memoryAvailableBytes": memory_available,
        "storageTotalBytes": storage.total,
        "storageAvailableBytes": storage.free,
        "ethernet": _interface("eth0"),
        "wifi": _interface("wlan0"),
        "ipv6": _has_global_ipv6(),
        "bluetooth": Path("/sys/class/bluetooth").exists(),
        "systemState": _system_state(),
        "services": [
            {"id": service_id, "status": _service_status(unit)}
            for service_id, unit in SERVICE_UNITS.items()
        ],
    }


def platform_identity() -> dict[str, str]:
    os_release = _os_release()
    return {
        "hostname": socket.gethostname().lower(),
        "osName": os_release.get("PRETTY_NAME", os_release.get("NAME", "Linux")),
        "osVersion": os_release.get("VERSION_ID", "unknown"),
        "architecture": _command(["uname", "-m"], "unknown"),
    }


def _memory() -> tuple[int, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", maxsplit=1)
        values[key] = int(raw.strip().split()[0]) * 1024
    return values["MemTotal"], values["MemAvailable"]


def _temperature() -> float | None:
    path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return round(int(path.read_text(encoding="utf-8").strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def _throttled() -> bool:
    value = _command(["vcgencmd", "get_throttled"], "")
    try:
        return int(value.removeprefix("throttled="), 16) != 0
    except ValueError:
        return False


def _interface(name: str) -> dict[str, bool]:
    path = Path("/sys/class/net") / name
    if not path.exists():
        return {"present": False, "connected": False}
    try:
        connected = (path / "operstate").read_text(encoding="utf-8").strip() == "up"
    except OSError:
        connected = False
    return {"present": True, "connected": connected}


def _has_global_ipv6() -> bool:
    try:
        rows = Path("/proc/net/if_inet6").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return any(row.split()[-1] != "lo" and not row.startswith("fe80") for row in rows)


def _system_state() -> str:
    value = _command(["systemctl", "is-system-running"], "unknown")
    if value == "degraded":
        failed_output = _command(
            ["systemctl", "--failed", "--no-legend", "--plain"], "unknown"
        )
        failed_units = {
            line.split()[0]
            for line in failed_output.splitlines()
            if line.split() and line != "unknown"
        }
        if failed_units and failed_units <= NON_RUNTIME_FAILED_UNITS:
            return "running"
    return value if value in {"running", "degraded", "maintenance"} else "unknown"


def _service_status(unit: str) -> str:
    load_state = _command(
        ["systemctl", "show", unit, "--property=LoadState", "--value"], "not-found"
    )
    if load_state == "not-found":
        return "not_configured"
    active_state = _command(["systemctl", "is-active", unit], "unknown")
    if active_state == "active":
        return "ready"
    if active_state == "failed":
        return "degraded"
    return "unavailable"


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key] = value.strip().strip('"')
    return values


def _command(command: list[str], fallback: str) -> str:
    try:
        result = subprocess.run(command, capture_output=True, check=False, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return fallback
    return result.stdout.strip() or fallback
