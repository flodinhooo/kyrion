from __future__ import annotations

import colorsys
import re
import subprocess

MELK_NAME = "MELK-OA20"
MAC_PATTERN = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
COMMAND_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"


class BluetoothLightError(RuntimeError):
    pass


def known_melk_lights() -> list[dict[str, object]]:
    result = _run(["bluetoothctl", "devices"])
    lights: list[dict[str, object]] = []
    for row in result.stdout.splitlines()[:100]:
        parts = row.split(maxsplit=2)
        if len(parts) != 3 or parts[0] != "Device" or parts[2] != MELK_NAME:
            continue
        address = parts[1].upper()
        if not MAC_PATTERN.fullmatch(address):
            continue
        lights.append({
            "address": address,
            "name": MELK_NAME,
            "model": "OA20",
            "supported": True,
            "on": None,
            "brightness": None,
            "hue": None,
            "saturation": None,
        })
    return lights


def set_power(address: str, on: bool) -> None:
    _write(address, [0x7E, 0x04, 0x04, int(on), 0x00, int(on), 0xFF, 0x00, 0xEF])


def set_brightness(address: str, brightness: int) -> None:
    if brightness not in range(0, 101):
        raise BluetoothLightError("invalid brightness")
    raw = round(brightness * 255 / 100)
    _write(address, [0x7E, 0x04, 0x01, raw, 0x01, 0xFF, 0xFF, 0x00, 0xEF])


def set_colour(address: str, hue: int, saturation: int) -> None:
    if hue not in range(0, 361) or saturation not in range(0, 101):
        raise BluetoothLightError("invalid colour")
    red, green, blue = (
        round(channel * 255)
        for channel in colorsys.hsv_to_rgb((hue % 360) / 360, saturation / 100, 1)
    )
    _write(address, [0x7E, 0x04, 0x04, 0xE0, 0x01, 0x01, 0xFF, 0x00, 0xEF])
    _write(address, [0x7E, 0x07, 0x05, 0x03, red, green, blue, 0x10, 0xEF])


def _write(address: str, packet: list[int]) -> None:
    normalized = address.upper()
    if not MAC_PATTERN.fullmatch(normalized) or len(packet) != 9 or any(
        byte not in range(256) for byte in packet
    ):
        raise BluetoothLightError("invalid command")
    info = _run(["bluetoothctl", "info", normalized])
    if f"Name: {MELK_NAME}" not in info.stdout:
        raise BluetoothLightError("unsupported device")
    if "Connected: yes" not in info.stdout:
        connected = _run(["bluetoothctl", "connect", normalized], timeout=8)
        if connected.returncode != 0 or "Connection successful" not in connected.stdout:
            raise BluetoothLightError("device unavailable")
    device_path = normalized.replace(":", "_")
    characteristic = (
        f"/org/bluez/hci0/dev_{device_path}/service000c/char000d"
    )
    result = _run([
        "busctl", "call", "org.bluez", characteristic,
        "org.bluez.GattCharacteristic1", "WriteValue", "aya{sv}",
        str(len(packet)), *(str(byte) for byte in packet), "1", "type", "s", "command",
    ])
    if result.returncode != 0:
        raise BluetoothLightError("bluetooth write failed")


def _run(command: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, capture_output=True, check=False, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise BluetoothLightError("bluetooth operation failed") from error
