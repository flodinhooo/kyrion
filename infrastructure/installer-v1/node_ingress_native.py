"""Native owned-service adapter for the existing agent-ingress transaction."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from authority import pending_ingress_format, require_active
from bundle import sha256, unique_object
from host import reject_links
from node_ingress import FILE, KEY, ComposeRuntime, require_workers, transition


def role_allowed(root: Path, state: dict, role: str) -> bool:
    """Narrow startup exception; never authorizes ordinary pending maintenance."""
    value = state.get(KEY)
    if value is None or (
        isinstance(value, dict) and value.get("phase") in {"verified", "recovered"}
    ):
        return False
    require_active(state, ingress=True)
    if state.get("backend") != "windows-native" or not pending_ingress_format(state):
        raise ValueError("E_AGENT_INGRESS_JOURNAL")
    view = SimpleNamespace(
        target=root, state=state, configuration=state["configuration"]
    )
    value = transition(view)
    if value["phase"] == "restored" and role in {"core", "web", "caddy"}:
        expected = value["beforeSha256"]
    elif value["phase"] in {"published", "started"} and role == "caddy":
        expected = value["afterSha256"]
    else:
        raise ValueError("E_AGENT_INGRESS_PENDING")
    path = root / FILE
    reject_links(path)
    if (
        not path.is_file()
        or path.stat().st_size > 16384
        or path.stat().st_nlink != 1
        or state["files"].get(FILE) != expected
        or sha256(path) != expected
    ):
        raise ValueError("E_AGENT_INGRESS_CUSTOM")
    return True


def verify_payload(installation) -> None:
    from restore_platform import verify_native_tools

    files = installation.state["files"]
    installation.state["files"] = {
        name: value for name, value in files.items() if name != FILE
    }
    try:
        verify_native_tools(
            installation, prefixes=("runtime/caddy/", "runtime/installer/")
        )
    finally:
        installation.state["files"] = files


class NativeRuntime(ComposeRuntime):
    def __init__(self, installation):
        from native_runtime import plan_for
        from operational_restore import require_admin
        from windows_service import ROLES, ServiceManager
        from windows_system import base_environment

        if os.name != "nt":
            raise ValueError("E_AGENT_INGRESS_PLATFORM")
        require_admin()
        self.installation = installation
        root = installation.target
        require_workers(installation)
        verify_payload(installation)
        with ServiceManager() as scm:
            for role in ROLES:
                plan = plan_for(installation, role)
                with scm.opened(plan["name"]) as handle:
                    if not handle:
                        raise ValueError("E_NATIVE_SERVICE_MISSING")
                    scm.assert_owned(handle, plan)
        worker = root / "payload/runtime/installer/kyrion-service.exe"
        reject_links(worker)
        response = subprocess.run(
            [str(worker), "--capabilities"],
            cwd=root,
            env=base_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if response.returncode or len(response.stdout) > 16384:
            raise ValueError("E_AGENT_INGRESS_HOST_UPGRADE")
        try:
            capability = json.loads(response.stdout, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError):
            raise ValueError("E_AGENT_INGRESS_HOST_UPGRADE") from None
        if (
            not isinstance(capability, dict)
            or type(capability.get("formatVersion")) is not int
            or capability["formatVersion"] != 1
            or capability.get("agentIngressFence") is not True
            or type(capability.get("nativeAgentIngressVersion")) is not int
            or capability["nativeAgentIngressVersion"] != 1
        ):
            raise ValueError("E_AGENT_INGRESS_HOST_UPGRADE")

    def validate(self, text: str) -> None:
        from windows_system import base_environment

        root = self.installation.target
        if not isinstance(text, str) or len(text.encode()) > 16384:
            raise ValueError("E_AGENT_INGRESS_CUSTOM")
        result = subprocess.run(
            [
                str(root / "payload/runtime/caddy/caddy.exe"),
                "validate",
                "--config",
                "-",
                "--adapter",
                "caddyfile",
            ],
            cwd=root,
            env=base_environment(),
            input=text.encode(),
            capture_output=True,
            timeout=45,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise ValueError("E_AGENT_INGRESS_RUNTIME")

    def service(self, *, start: bool) -> None:
        from native_runtime import plan_for
        from windows_service import ServiceManager

        plan = plan_for(self.installation, "caddy")
        with (
            ServiceManager(writable=True) as scm,
            scm.opened(plan["name"], mutate=True) as handle,
        ):
            if not handle:
                raise ValueError("E_NATIVE_SERVICE_MISSING")
            if start:
                scm.start(handle, plan)
            else:
                scm.stop(handle, plan)

    def stop(self) -> None:
        self.service(start=False)

    def start(self) -> None:
        self.service(start=True)
