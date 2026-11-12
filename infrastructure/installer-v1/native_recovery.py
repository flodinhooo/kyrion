"""Run the existing Core host-only recovery tool on owned native Windows data."""

from __future__ import annotations

import os
import subprocess
import uuid

from host import reject_links
from native_roles import read_configuration, role_plan
from native_runtime import permissions, plan_for, preflight, start_services
from windows_service import ServiceManager


def provision_owner_recovery(installation, space_id: str) -> None:
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    space_id = str(uuid.UUID(space_id))
    root = installation.target
    config = read_configuration(root)
    preflight(
        root, config["hostname"], config["address"], fresh=False, ports=config["ports"]
    )
    permissions(root, "verify")
    installation.verify_files()
    directory = root / "recovery"
    reject_links(directory)
    directory.mkdir(exist_ok=True)
    key = directory / (space_id + ".host-key")
    reject_links(key)
    if key.exists():
        raise ValueError("E_RECOVERY_EXISTING")
    executable, _, environment = role_plan(root, "core", config)
    arguments = [
        str(executable),
        "-Dloader.main=dev.kyrion.core.security.LocalSecurityAdmin",
        "-cp",
        str(root / "payload/app/core/core-runtime.jar"),
        "org.springframework.boot.loader.launch.PropertiesLauncher",
        "provision",
        space_id,
        str(key),
    ]
    # PostgreSQL stays available. Validate all ownership before any stop; no
    # HTTP recovery endpoint or separate identity/credential implementation.
    roles = ("caddy", "web", "core")
    with ServiceManager(writable=True) as scm:
        for role in roles:
            plan = plan_for(installation, role)
            with scm.opened(plan["name"], mutate=True) as handle:
                if not handle:
                    raise ValueError("E_NATIVE_SERVICE_MISSING")
                scm.assert_owned(handle, plan)
        try:
            for role in roles:
                plan = plan_for(installation, role)
                with scm.opened(plan["name"], mutate=True) as handle:
                    scm.stop(handle, plan)
            # Inherit the actual terminal: Core requires System.console(), asks
            # for the OWNER password, verifies the audit chain and shows code
            # once. Never capture, pipe, journal or print that code ourselves.
            result = subprocess.run(arguments, cwd=root, env=environment, check=False)
            reject_links(key)
            if result.returncode or not key.is_file() or key.stat().st_size != 43:
                raise ValueError("E_RECOVERY_NOT_PROVISIONED")
            installation.state["recovery"] = "provisioned-by-core-host-tool"
            installation.save()
        finally:
            start_services(installation)
