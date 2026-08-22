from __future__ import annotations

import argparse
import json
import logging
import subprocess
import threading
import time
from pathlib import Path

from kyrion_gateway_agent.bluetooth import (
    BluetoothLightError,
    set_brightness,
    set_colour,
    set_power,
)
from kyrion_gateway_agent.client import (
    CoreRequestError,
    button_event,
    complete_command,
    enroll,
    heartbeat,
    next_command,
)
from kyrion_gateway_agent.config import DEFAULT_CONFIG_PATH, AgentConfig
from kyrion_gateway_agent.health import collect_health, platform_identity

LOGGER = logging.getLogger("kyrion-gateway-agent")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kyrion gateway agent")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    enrollment = subparsers.add_parser("enroll")
    enrollment.add_argument("--core-url", required=True)
    enrollment.add_argument("--token", required=True)
    subparsers.add_parser("once")
    runner = subparsers.add_parser("run")
    runner.add_argument("--interval", type=int, default=15)
    runner.add_argument("--command-interval", type=float, default=0.25)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "enroll":
        result = enroll(args.core_url, args.token, platform_identity())
        config = AgentConfig(args.core_url.rstrip("/"), result.node_id, result.gateway_token)
        config.save(args.config)
        LOGGER.info("Gateway enrollment completed for node %s", result.node_id)
        return

    config = AgentConfig.load(args.config)
    if args.command == "once":
        heartbeat(config, collect_health())
        LOGGER.info("Gateway heartbeat completed")
        return

    heartbeat_interval = max(5, min(args.interval, 60))
    command_interval = max(0.1, min(args.command_interval, 2.0))
    next_heartbeat_at = 0.0
    threading.Thread(
        target=_forward_button_events,
        args=(config,),
        daemon=True,
        name="zigbee-button-events",
    ).start()
    while True:
        try:
            for _ in range(5):
                command = next_command(config)
                if command is None:
                    break
                _execute_command(config, command)
            now = time.monotonic()
            if now >= next_heartbeat_at:
                heartbeat(config, collect_health())
                LOGGER.info("Gateway heartbeat completed")
                next_heartbeat_at = now + heartbeat_interval
        except CoreRequestError as error:
            LOGGER.warning("Gateway communication failed: %s", error)
            next_heartbeat_at = 0.0
            time.sleep(min(heartbeat_interval, 5))
            continue
        time.sleep(command_interval)


def _forward_button_events(config: AgentConfig) -> None:
    while True:
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                ["mosquitto_sub", "-h", "127.0.0.1", "-t", "zigbee2mqtt/+", "-v"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
            if process.stdout is None:
                raise RuntimeError("mqtt subscription unavailable")
            for line in process.stdout:
                topic, separator, raw_payload = line.rstrip("\n").partition(" ")
                if not separator:
                    continue
                try:
                    payload = json.loads(raw_payload)
                except json.JSONDecodeError:
                    continue
                action = payload.get("action") if isinstance(payload, dict) else None
                if action not in {"single", "double", "long"}:
                    continue
                friendly_name = topic.removeprefix("zigbee2mqtt/")
                health = collect_health()
                devices = health.get("zigbee", {}).get("devices", [])
                device = next(
                    (item for item in devices if item.get("friendlyName") == friendly_name),
                    None,
                )
                device_id = device.get("ieeeAddress") if isinstance(device, dict) else None
                if not isinstance(device_id, str):
                    LOGGER.warning(
                        "Ignoring button event from unknown Zigbee topic %s",
                        friendly_name[:80],
                    )
                    continue
                try:
                    button_event(config, device_id, action)
                    LOGGER.info("Forwarded Zigbee button event %s for %s", action, device_id)
                except CoreRequestError as error:
                    LOGGER.warning("Button event forwarding failed: %s", error)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            LOGGER.warning("Zigbee button subscription failed: %s", error)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
        time.sleep(2)


def _execute_command(config: AgentConfig, command: dict[str, object]) -> None:
    command_id = str(command["id"])
    kind = command.get("type")
    payload = command.get("payload")
    if not isinstance(payload, dict):
        complete_command(config, command_id, False, "INVALID_PAYLOAD")
        return
    try:
        if kind in {"bluetooth.power", "bluetooth.brightness", "bluetooth.color"}:
            address = str(payload["deviceId"])
            if kind == "bluetooth.power":
                if not isinstance(payload.get("on"), bool):
                    raise ValueError("invalid power")
                set_power(address, payload["on"])
            elif kind == "bluetooth.brightness":
                set_brightness(address, int(payload["brightness"]))
            else:
                set_colour(address, int(payload["hue"]), int(payload["saturation"]))
            complete_command(config, command_id, True)
            return
        if kind == "zigbee.permit_join":
            duration = int(payload["duration"])
            topic = "zigbee2mqtt/bridge/request/permit_join"
            body = {"value": duration > 0, "time": duration}
        elif kind == "zigbee.remove":
            device = str(payload["deviceId"])
            if not device.startswith("0x") or len(device) != 18:
                raise ValueError("invalid device")
            topic = "zigbee2mqtt/bridge/request/device/remove"
            body = {"id": device, "force": True}
        elif kind in {
            "zigbee.power", "zigbee.brightness", "zigbee.color",
            "zigbee.hue_power_on_recover",
        }:
            device = str(payload["deviceId"])
            if not device.startswith("0x") or len(device) != 18:
                raise ValueError("invalid device")
            topic = f"zigbee2mqtt/{device}/set"
            if kind == "zigbee.power":
                body = {"state": "ON" if payload["on"] is True else "OFF"}
            elif kind == "zigbee.brightness":
                body = {"brightness": int(payload["brightness"])}
            elif kind == "zigbee.hue_power_on_recover":
                body = {"hue_power_on_behavior": "recover"}
            else:
                body = {
                    "color": {
                        "hue": int(payload["hue"]),
                        "saturation": int(payload["saturation"]),
                    }
                }
        else:
            raise ValueError("unsupported command")
        result = subprocess.run(
            ["mosquitto_pub", "-h", "127.0.0.1", "-t", topic, "-m", json.dumps(body)],
            capture_output=True, check=False, timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError("mqtt publish failed")
        if kind == "zigbee.power":
            _confirm_power_state(device, body["state"])
        complete_command(config, command_id, True)
    except (
        KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError, RuntimeError,
        BluetoothLightError,
    ) as error:
        LOGGER.warning(
            "Gateway command %s failed locally: %s %s",
            command_id, type(error).__name__, str(error)[:80],
        )
        complete_command(config, command_id, False, "EXECUTION_FAILED")


def _confirm_power_state(device: str, expected: str) -> None:
    result = subprocess.run(
        [
            "mosquitto_sub", "-h", "127.0.0.1", "-t", f"zigbee2mqtt/{device}",
            "-C", "1", "-W", "7",
        ],
        capture_output=True, check=False, timeout=9, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("device state confirmation timed out")
    state = json.loads(result.stdout).get("state")
    if state != expected:
        raise RuntimeError(f"device reported state {state!r} instead of {expected!r}")


if __name__ == "__main__":
    main()
