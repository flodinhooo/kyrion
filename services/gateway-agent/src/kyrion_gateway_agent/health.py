from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
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
        "adapters": _serial_adapters(),
        "zigbee": _zigbee_health(),
        "services": [
            {"id": service_id, "status": _service_status(unit)}
            for service_id, unit in SERVICE_UNITS.items()
        ],
    }


def _serial_adapters() -> list[dict[str, str]]:
    serial_root = Path("/dev/serial/by-id")
    try:
        paths = sorted(serial_root.iterdir())
    except OSError:
        return []

    adapters: list[dict[str, str]] = []
    for path in paths[:16]:
        name = path.name
        if "Sonoff_Zigbee_3.0_USB_Dongle_Plus_V2" not in name:
            continue
        serial = name.removeprefix("usb-Itead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_V2_")
        serial = serial.removesuffix("-if00-port0")
        adapters.append(
            {
                "id": name,
                "protocol": "zigbee",
                "vendor": "Itead",
                "model": "Sonoff Zigbee 3.0 USB Dongle Plus V2",
                "serial": serial,
                "path": str(path),
            }
        )
    return adapters


def _zigbee_health() -> dict[str, Any] | None:
    raw_devices = _command(
        [
            "mosquitto_sub", "-h", "127.0.0.1", "-t",
            "zigbee2mqtt/bridge/devices", "-C", "1", "-W", "2",
        ],
        "",
    )
    raw_info = _command(
        ["mosquitto_sub", "-h", "127.0.0.1", "-t", "zigbee2mqtt/bridge/info", "-C", "1", "-W", "2"],
        "",
    )
    try:
        devices_value = json.loads(raw_devices)
        info = json.loads(raw_info)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(devices_value, list) or not isinstance(info, dict):
        return None
    devices: list[dict[str, Any]] = []
    for item in devices_value[:100]:
        if not isinstance(item, dict) or item.get("type") == "Coordinator":
            continue
        definition = item.get("definition") if isinstance(item.get("definition"), dict) else {}
        friendly_name = item.get("friendly_name")
        ieee_address = item.get("ieee_address")
        if not isinstance(friendly_name, str) or not isinstance(ieee_address, str):
            continue
        raw_state = _zigbee_device_state(friendly_name)
        try:
            state = json.loads(raw_state)
        except json.JSONDecodeError:
            state = {}
        devices.append({
            "ieeeAddress": ieee_address,
            "friendlyName": friendly_name,
            "vendor": str(definition.get("vendor", "Unknown"))[:100],
            "model": str(definition.get("model", "Unknown"))[:100],
            "description": str(definition.get("description", "Zigbee device"))[:200],
            "supported": bool(item.get("supported", False)),
            "on": (
                state.get("state") == "ON"
                if isinstance(state, dict) and state.get("state") in {"ON", "OFF"}
                else None
            ),
            "brightness": (
                state.get("brightness")
                if isinstance(state, dict) and isinstance(state.get("brightness"), int)
                else None
            ),
            "hue": (
                state.get("color", {}).get("hue")
                if isinstance(state, dict) and isinstance(state.get("color"), dict)
                and isinstance(state.get("color", {}).get("hue"), (int, float))
                else None
            ),
            "saturation": (
                state.get("color", {}).get("saturation")
                if isinstance(state, dict) and isinstance(state.get("color"), dict)
                and isinstance(state.get("color", {}).get("saturation"), (int, float))
                else None
            ),
            "colorTemperature": (
                state.get("color_temp")
                if isinstance(state, dict) and isinstance(state.get("color_temp"), int)
                else None
            ),
            "linkquality": (
                state.get("linkquality")
                if isinstance(state, dict) and isinstance(state.get("linkquality"), int)
                else None
            ),
        })
    return {
        "permitJoin": bool(info.get("permit_join", False)),
        "channel": int(info.get("network", {}).get("channel", 0)),
        "devices": devices,
    }


def _zigbee_device_state(friendly_name: str) -> str:
    subscriber: subprocess.Popen[str] | None = None
    try:
        subscriber = subprocess.Popen(
            [
                "mosquitto_sub", "-h", "127.0.0.1", "-t",
                f"zigbee2mqtt/{friendly_name}", "-C", "1", "-W", "2",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        time.sleep(0.5)
        subprocess.run(
            [
                "mosquitto_pub", "-h", "127.0.0.1", "-t",
                f"zigbee2mqtt/{friendly_name}/get", "-m",
                '{"state":"","brightness":"","color":"","color_temp":""}',
            ],
            capture_output=True, check=False, timeout=2,
        )
        stdout, _ = subscriber.communicate(timeout=3)
        return stdout.strip()
    except (OSError, subprocess.SubprocessError):
        if subscriber is not None:
            subscriber.kill()
        return ""


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
