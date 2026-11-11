"""Fixed machine-start tasks for the native Windows runtime backend.

The task principal is Local Service, never an interactive user. This module does
not claim cold-boot acceptance, install runtimes or execute arbitrary commands.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path, PureWindowsPath

NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
ROLES = frozenset({"core", "web", "caddy"})
ET.register_namespace("", NAMESPACE)


def task_plan(installation_id: str, target: str, role: str) -> dict[str, str]:
    identifier = str(uuid.UUID(installation_id))
    root = PureWindowsPath(target)
    if (
        role not in ROLES
        or not root.is_absolute()
        or root.drive.startswith("\\")
        or len(root.parts) < 3
        or len(str(root)) > 180
        or any(character in str(root) for character in '\r\n\x00"<>|?*')
        or any(
            part in {".", ".."} or part.endswith((" ", ".")) or ":" in part
            for part in root.parts[1:]
        )
    ):
        raise ValueError("E_WINDOWS_TASK_TARGET")
    command = str(root / "installer.exe")
    arguments = subprocess.list2cmdline(
        ["--supervise-role", role, "--target", str(root)]
    )
    name = "Kyrion-" + identifier + "-" + role
    description = "Managed by Kyrion installation " + identifier + "; role " + role
    task = ET.Element("Task", {"version": "1.4", "xmlns": NAMESPACE})

    def child(parent, name, value=None, **attributes):
        item = ET.SubElement(parent, name, attributes)
        if value is not None:
            item.text = value
        return item

    information = child(task, "RegistrationInfo")
    child(information, "Description", description)
    triggers = child(task, "Triggers")
    boot = child(triggers, "BootTrigger")
    child(boot, "Enabled", "true")
    child(boot, "Delay", "PT30S")
    principal = child(child(task, "Principals"), "Principal", id="KyrionRuntime")
    child(principal, "UserId", "S-1-5-19")
    # The XML schema cannot encode ServiceAccount. The native API explicitly
    # sets TASK_LOGON_SERVICE_ACCOUNT=5 after loading this fixed SID principal.
    child(principal, "RunLevel", "LeastPrivilege")
    child(principal, "ProcessTokenSidType", "Unrestricted")
    settings = child(task, "Settings")
    for key, value in (
        ("MultipleInstancesPolicy", "IgnoreNew"),
        ("DisallowStartIfOnBatteries", "false"),
        ("StopIfGoingOnBatteries", "false"),
        ("AllowHardTerminate", "true"),
        ("StartWhenAvailable", "true"),
        ("RunOnlyIfNetworkAvailable", "false"),
        ("RunOnlyIfIdle", "false"),
        ("AllowStartOnDemand", "true"),
        ("Enabled", "true"),
        ("Hidden", "true"),
        ("WakeToRun", "false"),
        ("ExecutionTimeLimit", "PT0S"),
    ):
        child(settings, key, value)
    restart = child(settings, "RestartOnFailure")
    child(restart, "Interval", "PT1M")
    child(restart, "Count", "3")
    action = child(child(task, "Actions", Context="KyrionRuntime"), "Exec")
    child(action, "Command", command)
    child(action, "Arguments", arguments)
    child(action, "WorkingDirectory", str(root))
    return {
        "name": name,
        "xml": ET.tostring(task, encoding="unicode"),
        "command": command,
        "arguments": arguments,
        "directory": str(root),
        "description": description,
    }


def operate(plan: dict[str, str], action: str = "validate") -> dict:
    match = re.fullmatch(
        r"Kyrion-([a-f0-9-]{36})-(core|web|caddy)", plan.get("name", "")
    )
    if match is None or plan != task_plan(
        match[1], plan.get("directory", ""), match[2]
    ):
        raise ValueError("E_WINDOWS_TASK_PLAN")
    if os.name != "nt" or action not in {
        "validate",
        "inspect",
        "register",
        "start",
        "stop",
        "remove",
    }:
        raise ValueError("E_WINDOWS_TASK_OPERATION")
    powershell = (
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(Path(__file__).with_name("windows-tasks.ps1")),
            "-Action",
            action,
        ],
        input=json.dumps(plan, ensure_ascii=True).encode("utf-8"),
        capture_output=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode or len(result.stdout) > 16384:
        code = result.stderr.decode("ascii", errors="replace").strip()
        if re.fullmatch(r"E_TASK_[A-Z_]{1,60}", code):
            raise ValueError(code)
        raise ValueError("E_WINDOWS_TASK: native scheduler operation failed")
    value = json.loads(result.stdout.decode("utf-8-sig"))
    if (
        not isinstance(value, dict)
        or value.get("name") != plan["name"]
        or value.get("action") != action
        or value.get("coldBootVerified") is not False
    ):
        raise ValueError("E_WINDOWS_TASK_RESPONSE")
    return value
