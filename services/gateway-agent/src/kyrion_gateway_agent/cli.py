from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
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
    motion_event,
    next_command,
)
from kyrion_gateway_agent.config import DEFAULT_CONFIG_PATH, AgentConfig
from kyrion_gateway_agent.health import collect_health, platform_identity

LOGGER = logging.getLogger("kyrion-gateway-agent")
_youtube_process: subprocess.Popen[str] | None = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Kyrion gateway agent")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    enrollment = subparsers.add_parser("enroll")
    enrollment.add_argument("--core-url", required=True)
    enrollment.add_argument("--token", required=True)
    prepared = subparsers.add_parser("enroll-prepared")
    prepared.add_argument("--core-url")
    prepared.add_argument("--token-file", type=Path)
    prepared.add_argument("--ca-certificate", type=Path)
    subparsers.add_parser("once")
    runner = subparsers.add_parser("run")
    runner.add_argument("--interval", type=int, default=15)
    runner.add_argument("--command-interval", type=float, default=0.25)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "enroll-prepared":
        from kyrion_gateway_agent.enrollment import enroll_prepared

        if os.name != "posix":
            raise ValueError("E_AGENT_PLATFORM")
        config = enroll_prepared(
            args.config,
            url=args.core_url,
            token_file=args.token_file,
            certificate=args.ca_certificate,
            identity=platform_identity(),
        )
        print(json.dumps({"nodeId": config.node_id, "paired": True}))
        return

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

    if config.local_only:
        from kyrion_gateway_agent.enrollment import runtime_lock

        with runtime_lock(args.config):
            run_prepared(config, interval=args.interval, command_interval=args.command_interval)
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


def run_prepared(
    config: AgentConfig, *, interval: int = 15, command_interval: float = 0.25
) -> None:
    from kyrion_gateway_agent.prepared_runtime import run

    run(
        config,
        _execute_command,
        _forward_button_events,
        interval=interval,
        command_interval=command_interval,
    )


def _scoped_event_lines(
    process: subprocess.Popen[bytes], allowed: Callable[[], bool], stopped: threading.Event
) -> Iterator[str]:
    import selectors

    if process.stdout is None:
        return
    pending = b""
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while not stopped.is_set() and allowed():
            if not selector.select(timeout=0.5):
                continue
            block = os.read(process.stdout.fileno(), 4096)
            if not block:
                return
            pending += block
            if len(pending) > 65536:
                return
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                if len(line) > 16384:
                    continue
                try:
                    yield line.decode("utf-8")
                except UnicodeDecodeError:
                    continue


def _forward_button_events(
    config: AgentConfig,
    allowed: Callable[[], bool] | None = None,
    stopped: threading.Event | None = None,
    register_child: Callable[[subprocess.Popen[bytes] | None], None] | None = None,
) -> None:
    from kyrion_gateway_agent.prepared_runtime import stop_child

    stopped = stopped if stopped is not None else threading.Event()
    while not stopped.is_set():
        if allowed is not None and not allowed():
            stopped.wait(0.5)
            continue
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                ["mosquitto_sub", "-h", "127.0.0.1", "-t", "zigbee2mqtt/+", "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=False,
            )
            if register_child is not None:
                register_child(process)
            if process.stdout is None:
                raise RuntimeError("mqtt subscription unavailable")
            lines = (
                (line.decode("utf-8") for line in process.stdout)
                if allowed is None
                else _scoped_event_lines(process, allowed, stopped)
            )
            for line in lines:
                if stopped.is_set() or (allowed is not None and not allowed()):
                    break
                topic, separator, raw_payload = line.rstrip("\n").partition(" ")
                if not separator:
                    continue
                try:
                    payload = json.loads(raw_payload)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                action = payload.get("action")
                occupancy = payload.get("occupancy")
                if action not in {"single", "double", "long"} and not isinstance(occupancy, bool):
                    continue
                friendly_name = topic.removeprefix("zigbee2mqtt/")
                device_id = _resolve_zigbee_device_id(friendly_name, prepared=allowed is not None)
                if not isinstance(device_id, str):
                    LOGGER.warning("Ignoring event from unknown Zigbee topic")
                    continue
                try:
                    if action in {"single", "double", "long"}:
                        button_event(config, device_id, action)
                        LOGGER.info("Forwarded Zigbee button event %s for %s", action, device_id)
                    if isinstance(occupancy, bool):
                        motion_event(config, device_id, occupancy)
                        LOGGER.info(
                            "Forwarded Zigbee motion event %s for %s",
                            "detected" if occupancy else "clear",
                            device_id,
                        )
                except CoreRequestError as error:
                    LOGGER.warning("Zigbee event forwarding failed: %s", error)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            LOGGER.warning("Zigbee button subscription failed: %s", error)
        finally:
            if process is not None and process.poll() is None:
                stop_child(process)
            if process is not None and process.stdout is not None:
                process.stdout.close()
            if register_child is not None:
                register_child(None)
        stopped.wait(2)


def _resolve_zigbee_device_id(friendly_name: str, *, prepared: bool = False) -> str | None:
    if len(friendly_name) == 18 and friendly_name.startswith("0x"):
        return friendly_name
    health = collect_health(include_voice=not prepared)
    devices = health.get("zigbee", {}).get("devices", [])
    device = next(
        (item for item in devices if item.get("friendlyName") == friendly_name),
        None,
    )
    return device.get("ieeeAddress") if isinstance(device, dict) else None


def _execute_command(config: AgentConfig, command: dict[str, object]) -> None:
    command_id = str(command["id"])
    kind = command.get("type")
    payload = command.get("payload")
    if not isinstance(payload, dict):
        complete_command(config, command_id, False, "INVALID_PAYLOAD")
        return
    try:
        if kind == "youtube.play":
            _play_youtube(payload)
            complete_command(config, command_id, True)
            return
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
            "zigbee.power",
            "zigbee.brightness",
            "zigbee.color",
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
        if kind == "zigbee.power":
            _publish_and_confirm_power(topic, body, device, body["state"])
        else:
            result = subprocess.run(
                ["mosquitto_pub", "-h", "127.0.0.1", "-t", topic, "-m", json.dumps(body)],
                capture_output=True,
                check=False,
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError("mqtt publish failed")
        complete_command(config, command_id, True)
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        subprocess.SubprocessError,
        RuntimeError,
        BluetoothLightError,
    ) as error:
        LOGGER.warning(
            "Gateway command %s failed locally: %s %s",
            command_id,
            type(error).__name__,
            str(error)[:80],
        )
        complete_command(config, command_id, False, "EXECUTION_FAILED")


def _play_youtube(payload: dict[str, object]) -> None:
    global _youtube_process
    url = payload.get("url")
    output_id = payload.get("outputId")
    if (
        not isinstance(url, str)
        or not url.startswith(("https://www.youtube.com/", "https://music.youtube.com/"))
        or len(url) > 2048
    ):
        raise ValueError("invalid YouTube URL")
    if not isinstance(output_id, str) or not output_id or len(output_id) > 200:
        raise ValueError("invalid audio output")
    media_port = int(os.getenv("KYRION_MEDIA_PORT", "18765"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(("127.0.0.1", media_port))
        connection.sendall(json.dumps({"url": url, "outputId": output_id}).encode())
        if connection.recv(32).strip() != b"OK":
            raise RuntimeError("media player rejected request")


def _publish_and_confirm_power(
    topic: str, body: dict[str, object], device: str, expected: str
) -> None:
    subscriber = subprocess.Popen(
        [
            "mosquitto_sub",
            "-h",
            "127.0.0.1",
            "-t",
            f"zigbee2mqtt/{device}",
            "-R",
            "-C",
            "1",
            "-W",
            "7",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(0.05)
        result = subprocess.run(
            ["mosquitto_pub", "-h", "127.0.0.1", "-t", topic, "-m", json.dumps(body)],
            capture_output=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError("mqtt publish failed")
        output, _ = subscriber.communicate(timeout=9)
        if subscriber.returncode != 0:
            raise RuntimeError("device state confirmation timed out")
        state = json.loads(output).get("state")
        if state != expected:
            raise RuntimeError(f"device reported state {state!r} instead of {expected!r}")
    finally:
        if subscriber.poll() is None:
            subscriber.terminate()


if __name__ == "__main__":
    main()
