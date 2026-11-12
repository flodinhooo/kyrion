"""Run the existing Core host-only recovery tool on owned native Windows data."""

from __future__ import annotations

import os
import secrets
import subprocess
import uuid

from bundle import sha256
from host import reject_links
from native_roles import read_configuration, role_plan
from native_runtime import permissions, plan_for, preflight, start_services
from windows_service import ServiceManager


def provision_owner_recovery(installation, space_id: str) -> None:
    owner_recovery(installation, space_id, "provision")


def prepare_key(installation, space_id: str):
    from windows_security import create_private_directory, open_secured_file

    directory = installation.target / "recovery"
    reject_links(directory)
    if not directory.exists():
        create_private_directory(directory)
    permissions(installation.target, "verify-recovery")
    key = directory / (space_id + ".host-key")
    reject_links(key)
    recorded = installation.state.get("recoveryKey")
    if key.exists():
        if recorded != {"spaceId": space_id, "sha256": sha256(key)}:
            raise ValueError("E_RECOVERY_EXISTING")
        if installation.state.get("recoveryKeyPending") is True:
            installation.state["recoveryKeyPending"] = False
            installation.save()
        return key
    if recorded is not None and recorded.get("spaceId") != space_id:
        raise ValueError("E_RECOVERY_EXISTING")
    if (
        recorded is not None
        and installation.state.get("recoveryKeyPending") is not True
    ):
        raise ValueError("E_RECOVERY_KEY_MISSING")
    material = secrets.token_urlsafe(32).encode("ascii")
    import hashlib

    installation.state["recoveryKey"] = {
        "spaceId": space_id,
        "sha256": hashlib.sha256(material).hexdigest(),
    }
    installation.state["recoveryKeyPending"] = True
    installation.save()
    descriptor = open_secured_file(key, directory)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    installation.state["recoveryKeyPending"] = False
    installation.save()
    permissions(installation.target, "verify-recovery")
    return key


def owner_recovery(installation, space_id: str, command: str) -> None:
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    if command not in {"provision", "open", "complete", "rotate"}:
        raise ValueError("E_RECOVERY_COMMAND")
    space_id = str(uuid.UUID(space_id))
    root = installation.target
    config = read_configuration(root)
    preflight(
        root, config["hostname"], config["address"], fresh=False, ports=config["ports"]
    )
    permissions(root, "verify")
    installation.verify_files()
    key = root / "recovery" / (space_id + ".host-key")
    reject_links(key)
    if command != "provision":
        permissions(root, "verify-recovery")
        if not key.is_file() or installation.state.get("recoveryKey") != {
            "spaceId": space_id,
            "sha256": sha256(key),
        }:
            raise ValueError("E_RECOVERY_KEY_MISSING")
    executable, _, environment = role_plan(root, "core", config)
    arguments = [
        str(executable),
        "-Dloader.main=dev.kyrion.core.security.LocalSecurityAdmin",
        "-cp",
        str(root / "payload/app/core/core-runtime.jar"),
        "org.springframework.boot.loader.launch.PropertiesLauncher",
        "provision-prepared" if command == "provision" else command,
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
        if command == "provision":
            prepare_key(installation, space_id)
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
            permissions(root, "verify-recovery")
            installation.state["recovery"] = (
                "provisioned-by-core-host-tool"
                if command == "provision"
                else "completed-by-core-host-tool"
                if command == "complete"
                else "rotated-by-core-host-tool"
                if command == "rotate"
                else "one-use-session-opened-by-core-host-tool"
            )
            installation.save()
        finally:
            start_services(installation)
