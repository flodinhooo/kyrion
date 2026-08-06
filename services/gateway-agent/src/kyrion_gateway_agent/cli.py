from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from kyrion_gateway_agent.client import CoreRequestError, complete_command, enroll, heartbeat, next_command
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

    interval = max(5, min(args.interval, 60))
    while True:
        try:
            heartbeat(config, collect_health())
            command = next_command(config)
            if command is not None:
                _execute_command(config, command)
            LOGGER.info("Gateway heartbeat completed")
        except CoreRequestError as error:
            LOGGER.warning("Gateway heartbeat failed: %s", error)
        time.sleep(interval)


def _execute_command(config: AgentConfig, command: dict[str, object]) -> None:
    command_id = str(command["id"])
    kind = command.get("type")
    payload = command.get("payload")
    if not isinstance(payload, dict):
        complete_command(config, command_id, False, "INVALID_PAYLOAD")
        return
    try:
        if kind == "zigbee.permit_join":
            duration = int(payload["duration"])
            topic = "zigbee2mqtt/bridge/request/permit_join"
            body = {"value": duration > 0, "time": duration}
        elif kind in {"zigbee.power", "zigbee.brightness", "zigbee.color"}:
            device = str(payload["deviceId"])
            if not device.startswith("0x") or len(device) != 18:
                raise ValueError("invalid device")
            topic = f"zigbee2mqtt/{device}/set"
            if kind == "zigbee.power":
                body = {"state": "ON" if payload["on"] is True else "OFF"}
            elif kind == "zigbee.brightness":
                body = {"brightness": int(payload["brightness"])}
            else:
                body = {"color": {"hue": int(payload["hue"]), "saturation": int(payload["saturation"])}}
        else:
            raise ValueError("unsupported command")
        result = subprocess.run(
            ["mosquitto_pub", "-h", "127.0.0.1", "-t", topic, "-m", json.dumps(body)],
            capture_output=True, check=False, timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError("mqtt publish failed")
        complete_command(config, command_id, True)
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError, RuntimeError):
        complete_command(config, command_id, False, "EXECUTION_FAILED")


if __name__ == "__main__":
    main()
