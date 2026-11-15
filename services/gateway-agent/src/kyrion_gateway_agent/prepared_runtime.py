"""Task-scoped mode of the existing gateway agent; Core remains authoritative."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from collections.abc import Callable

from kyrion_gateway_agent import client
from kyrion_gateway_agent.config import AgentConfig
from kyrion_gateway_agent.health import collect_health

LOGGER = logging.getLogger("kyrion-gateway-agent")


def stop_child(child: subprocess.Popen[bytes]) -> None:
    if child.poll() is None:
        try:
            child.terminate()
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=1)
        except ProcessLookupError:
            child.wait(timeout=1)


class PermissionGate:
    def __init__(self):
        self._lock = threading.Lock()
        self._lease: client.TaskLease | None = None

    def update(self, lease: client.TaskLease | None) -> None:
        with self._lock:
            self._lease = lease

    def allows(self, task: str) -> bool:
        with self._lock:
            lease = self._lease
        return lease is not None and lease.allows(task)


def run(
    config: AgentConfig,
    execute: Callable[[AgentConfig, dict[str, object]], None],
    forward_events: Callable[
        [
            AgentConfig,
            Callable[[], bool],
            threading.Event,
            Callable[[subprocess.Popen[bytes] | None], None],
        ],
        None,
    ],
    *,
    interval: int = 15,
    command_interval: float = 0.25,
    stop: threading.Event | None = None,
    report: Callable[[str], None] | None = None,
) -> None:
    if not sys.platform.startswith("linux") or not config.local_only:
        raise ValueError("E_AGENT_PLATFORM")
    stop = stop if stop is not None else threading.Event()
    gate = PermissionGate()
    child_lock = threading.Lock()
    active_child: subprocess.Popen[bytes] | None = None

    def register_child(child: subprocess.Popen[bytes] | None) -> None:
        nonlocal active_child
        with child_lock:
            late = child is not None and stop.is_set()
            if not late:
                active_child = child
        if late and child is not None:
            stop_child(child)

    worker = threading.Thread(
        target=forward_events,
        args=(config, lambda: gate.allows("integration"), stop, register_child),
        daemon=True,
    )
    worker.start()
    next_policy, next_heartbeat, failures = 0.0, 0.0, 0
    interval = max(5, min(interval, 60))
    command_interval = max(0.1, min(command_interval, 2.0))
    try:
        while not stop.is_set():
            try:
                now = time.monotonic()
                if now >= next_policy:
                    gate.update(client.task_policy(config))
                    next_policy = now + min(interval, 10)
                if gate.allows("integration"):
                    for _ in range(5):
                        if stop.is_set() or not gate.allows("integration"):
                            break
                        command = client.next_command(config)
                        if command is None:
                            break
                        if stop.is_set() or not gate.allows("integration"):
                            client.complete_command(
                                config, str(command["id"]), False, "TASK_LEASE_EXPIRED"
                            )
                            break
                        execute(config, command)
                if now >= next_heartbeat:
                    observed = collect_health(
                        include_integrations=gate.allows("integration"),
                        include_voice=gate.allows("voice"),
                    )
                    client.heartbeat(config, observed)
                    if report is not None:
                        report("connected")
                    next_heartbeat = now + interval
                failures = 0
                stop.wait(command_interval)
            except client.CoreRequestError as error:
                gate.update(None)
                if report is not None:
                    report("disconnected")
                if str(error) in {
                    "E_AGENT_URL",
                    "E_AGENT_TLS_REQUIRED",
                    "E_AGENT_TLS_CONFIGURATION",
                    "E_AGENT_TASK_POLICY_INVALID",
                    "E_AGENT_RESPONSE_LIMIT",
                }:
                    raise
                if error.status in {401, 403}:
                    raise client.CoreRequestError("E_AGENT_ACCESS_REVOKED", error.status) from error
                if error.status in {404, 405}:
                    raise client.CoreRequestError(
                        "E_AGENT_TASK_POLICY_UNSUPPORTED", error.status
                    ) from error
                failures += 1
                next_policy = next_heartbeat = 0.0
                LOGGER.warning("Prepared node connection interrupted; local task authority cleared")
                stop.wait(min(60, 2 ** min(failures, 6)))
    finally:
        gate.update(None)
        stop.set()
        with child_lock:
            child = active_child
        try:
            if child is not None:
                stop_child(child)
        finally:
            worker.join(timeout=15)
        if worker.is_alive():
            raise client.CoreRequestError("E_AGENT_EVENT_STOP_PENDING")
        if report is not None:
            report("stopped")
