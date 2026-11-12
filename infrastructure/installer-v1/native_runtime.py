"""Native Windows backend of the existing installer/journal, not another setup store."""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

from bundle import unique_object
from crypto_support import certificate, private_tls_key
from host import reject_links
from native_bundle import authenticated_review, unpack
from native_roles import healthy, read_configuration, validate_ports
from native_staging import stage_bundle
from runtime import Installation, atomic_json, installation_lock, validate_network
from windows_service import ROLES, ServiceManager, service_plan
from windows_system import base_environment, native_architecture, system_directory

DEFAULT_PORTS = {"postgres": 5432, "core": 8080, "web": 3000, "caddy": 443}


def preflight(
    target: Path, hostname: str, address: str, fresh=True, ports=None
) -> None:
    if (
        os.name != "nt"
        or sys.getwindowsversion().build < 22000
        or native_architecture() != "amd64"
    ):
        raise ValueError("E_NATIVE_WINDOWS_VERSION")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError("E_NATIVE_ELEVATION")
    # Frozen distributions include the audited primitives; no PATH executable.
    import cryptography  # noqa: F401

    ports = validate_ports(DEFAULT_PORTS if ports is None else ports)
    service_plan(str(uuid.uuid4()), str(target), "core", ports["postgres"])
    validate_network(hostname, address, allow_loopback=True)
    reject_links(target)
    if not target.parent.is_dir():
        raise ValueError("E_NATIVE_PARENT")
    if shutil.disk_usage(target.parent).free < 12 * 1024**3:
        raise ValueError("E_NATIVE_DISK")
    if fresh:
        if target.exists():
            raise ValueError("E_NATIVE_EXISTING")
        for role, port in (ports or DEFAULT_PORTS).items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind((address if role == "caddy" else "127.0.0.1", port))
            except OSError:
                raise ValueError("E_NATIVE_PORT_" + role.upper()) from None
    with ServiceManager():
        pass


def permissions(target: Path, action: str) -> None:
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    if action == "create":
        permissions(target, "plan-create")
        from windows_security import create_private_directory

        create_private_directory(target)
        permissions(target, "root-only")
        return
    root = system_directory() / "WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run(
        [
            str(root),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(Path(__file__).with_name("windows-permissions.ps1")),
            "-Action",
            action,
        ],
        input=json.dumps({"target": str(target)}).encode(),
        capture_output=True,
        timeout=180,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env=base_environment(),
    )
    if result.returncode:
        code = result.stderr.decode("ascii", errors="replace").strip()
        raise ValueError(
            code
            if code.startswith(("E_NATIVE_", "E_TASK_"))
            and code.replace("_", "").isalnum()
            else "E_NATIVE_SECURITY"
        )
    value = json.loads(result.stdout.decode("utf-8-sig"))
    if value != {"action": action, "protected": True}:
        raise ValueError("E_NATIVE_SECURITY_RESPONSE")


def create_journalled_root(target: Path, state: dict) -> None:
    staging = target.with_name(target.name + ".creating-" + state["installationId"])
    permissions(staging, "create")
    atomic_json(staging / "install-state.json", state)
    # Windows rename refuses an existing destination. Until publication this
    # private directory has no secrets, live runtime or externally used identity.
    reject_links(target)
    staging.rename(target)


def admin_environment(root: Path) -> dict[str, str]:
    result = base_environment()
    result["PATH"] = (
        str(root / "payload/runtime/postgres/bin") + ";" + str(system_directory())
    )
    temporary = root / "data/admin-temp"
    reject_links(temporary)
    temporary.mkdir(exist_ok=True)
    result["TEMP"] = result["TMP"] = str(temporary)
    result["PGPASSFILE"] = str(root / "secrets/pgpass")
    return result


def pg_run(
    installation: Installation, executable: str, *arguments: str, timeout=120
) -> bytes:
    root = installation.target
    path = root / "payload/runtime/postgres/bin" / executable
    installation.verify_files()
    # Native daemon helpers must not inherit captured pipes; append only to an
    # administrator-protected local log, never print untrusted child output.
    log = root / "native-operations.log"
    reject_links(log)
    with log.open("ab") as output:
        result = subprocess.run(
            [str(path), *arguments],
            cwd=root,
            env=admin_environment(root),
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=output,
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    if result.returncode:
        raise ValueError("E_NATIVE_POSTGRES_OPERATION")
    return b""


def configure(
    installation: Installation, manifest: dict, digest: str, ports=None
) -> None:
    root = installation.target
    config = {
        "formatVersion": 1,
        "hostname": installation.configuration["hostname"],
        "address": installation.configuration["address"],
        "ports": validate_ports(DEFAULT_PORTS if ports is None else ports),
    }
    installation.write("native-runtime.json", json.dumps(config, sort_keys=True))
    for role in (
        "postgres",
        "postgres-init",
        "core",
        "web",
        "caddy",
        "knowledge",
        "tls",
        "web-tls",
    ):
        directory = root / "data" / role
        reject_links(directory)
        directory.mkdir(parents=True, exist_ok=True)
    # Secret creation follows payload extraction so bootstrap expiry isn't spent
    # downloading/extracting the public runtime.
    for name in (
        "bootstrap.secret",
        "credential.key",
        "audit-integrity.key",
        "postgres-password",
    ):
        installation.write(
            "secrets/" + name,
            secrets.token_bytes(32)
            if name.endswith(".key")
            else secrets.token_urlsafe(32) + "\n",
        )
    installation.write("data/tls/key.pem", private_tls_key())
    key = (root / "data/tls/key.pem").read_bytes()
    installation.write(
        "data/tls/cert.pem", certificate(config["hostname"], config["address"], key)
    )
    installation.write("secrets/core-tls.key", private_tls_key())
    installation.write(
        "core-cert.pem",
        certificate(
            "localhost", "127.0.0.1", (root / "secrets/core-tls.key").read_bytes()
        ),
    )
    installation.write("data/web-tls/key.pem", private_tls_key())
    installation.write(
        "web-cert.pem",
        certificate(
            "localhost", "127.0.0.1", (root / "data/web-tls/key.pem").read_bytes()
        ),
    )
    installation.write(
        "data/Caddyfile",
        "{\n admin off\n persist_config off\n auto_https off\n}\nhttps://"
        + config["hostname"]
        + (
            ":" + str(config["ports"]["caddy"])
            if config["ports"]["caddy"] != 443
            else ""
        )
        + " {\n bind "
        + config["address"]
        + '\n tls "'
        + (root / "data/tls/cert.pem").as_posix()
        + '" "'
        + (root / "data/tls/key.pem").as_posix()
        + '"\n reverse_proxy https://127.0.0.1:'
        + str(config["ports"]["web"])
        + ' {\n transport http {\n tls_trust_pool file "'
        + (root / "web-cert.pem").as_posix()
        + '"\n }\n }\n}\n',
    )
    password = (root / "secrets/postgres-password").read_text().strip()
    installation.write(
        "secrets/pgpass",
        "127.0.0.1:"
        + str(config["ports"]["postgres"])
        + ":*:kyrion:"
        + password
        + "\n",
    )
    installation.write(
        "native-create-db.sql",
        "SELECT 'CREATE DATABASE kyrion' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='kyrion')\n\\gexec\n",
    )
    installation.state["stage"] = "configured"
    installation.save()


def plan_for(installation: Installation, role: str) -> dict:
    config = read_configuration(installation.target)
    return service_plan(
        installation.state["installationId"],
        str(installation.target),
        role,
        config["ports"]["postgres"],
    )


def bootstrap_database(
    installation: Installation, pending: Path, resume_only=False
) -> bool:
    root = installation.target
    plan = plan_for(installation, "postgres-init")
    result_path = root / "data/postgres-init/result.json"
    reject_links(pending)
    reject_links(result_path)
    with ServiceManager(writable=True) as scm:
        with scm.opened(plan["name"], mutate=True) as handle:
            exists = bool(handle)
            if handle:
                scm.assert_owned(handle, plan)
        if not exists and not resume_only:
            register_services(installation, bootstrap=True)
            permissions(root, "grant")
            with scm.opened(plan["name"], mutate=True) as handle:
                if not handle:
                    raise ValueError("E_NATIVE_SERVICE_MISSING")
                scm.activate(handle, plan)
                scm.begin(handle, plan)
            exists = True
        if exists:
            with scm.opened(plan["name"], mutate=True) as handle:
                scm.wait(handle, 1, 300)
                scm.remove(handle, plan)
            scm.wait_removed(plan["name"])
            installation.state["nativeServices"]["postgres"] = "creating"
            installation.save()
    if result_path.is_file() and result_path.stat().st_size <= 4096:
        result = json.loads(result_path.read_text(), object_pairs_hook=unique_object)
        if (
            result == {"status": "initialized", "pending": pending.name}
            and (pending / "PG_VERSION").is_file()
            and (pending / "PG_VERSION").read_text().strip() == "17"
            and (pending / "global/pg_control").is_file()
        ):
            pg_run(installation, "pg_controldata.exe", str(pending))
            return True
    if resume_only:
        return False
    raise ValueError("E_NATIVE_DATABASE_INITIALIZATION")


def initialize_database(installation: Installation) -> None:
    root = installation.target
    state = installation.state
    final = root / "data/postgres"
    for path in (final, final / "PG_VERSION", final / "global/pg_control"):
        reject_links(path)
    if state.get("nativeDatabase") == "initialized":
        if (
            not (final / "PG_VERSION").is_file()
            or (final / "PG_VERSION").read_text().strip() != "17"
        ):
            raise ValueError("E_NATIVE_DATABASE")
        return
    pending = state.get("nativeDatabasePending")
    if pending is not None:
        if (
            not isinstance(pending, str)
            or not pending.startswith("postgres-pending-")
            or str(uuid.UUID(pending[17:])) != pending[17:]
        ):
            raise ValueError("E_NATIVE_DATABASE_STATE")
        old = root / "data" / pending
        reject_links(old)
        if (
            final.exists()
            and (final / "global/pg_control").is_file()
            and not old.exists()
        ):
            pg_run(installation, "pg_controldata.exe", str(final))
            state["nativeDatabase"] = "initialized"
            state.pop("nativeDatabasePending")
            installation.save()
            return
        if old.exists():
            if bootstrap_database(installation, old, resume_only=True):
                if final.exists():
                    if any(final.iterdir()):
                        raise ValueError("E_NATIVE_EXISTING_DATABASE")
                    final.rmdir()
                old.rename(final)
                state["nativeDatabase"] = "initialized"
                state.pop("nativeDatabasePending")
                installation.save()
                return
            old.rename(root / "data" / ("preserved-init-" + str(uuid.uuid4())))
    if final.exists() and any(final.iterdir()):
        raise ValueError("E_NATIVE_EXISTING_DATABASE")
    final.mkdir(exist_ok=True)
    pending = "postgres-pending-" + str(uuid.uuid4())
    state["nativeDatabasePending"] = pending
    installation.save()
    working = root / "data" / pending
    working.mkdir()
    bootstrap_database(installation, working)
    final.rmdir()
    working.rename(final)
    state["nativeDatabase"] = "initialized"
    state.pop("nativeDatabasePending")
    installation.save()


def register_services(
    installation: Installation, repair: bool = False, bootstrap: bool = False
) -> None:
    root = installation.target
    intents = installation.state.setdefault("nativeServices", {})
    with ServiceManager(writable=True) as scm:
        for role in ROLES:
            plan = plan_for(
                installation,
                "postgres-init" if bootstrap and role == "postgres" else role,
            )
            with scm.opened(plan["name"], mutate=True) as existing:
                if existing:
                    if intents.get(role) == "creating":
                        scm.configure(existing, plan)
                    scm.assert_owned(existing, plan)
                    intents[role] = (
                        "bootstrap"
                        if bootstrap and role == "postgres"
                        else "registered"
                    )
                    installation.save()
                    continue
            if not repair and role in intents and intents[role] != "creating":
                raise ValueError("E_NATIVE_SERVICE_MISSING")
            intents[role] = "creating"
            installation.save()
            if role == "postgres" and not bootstrap:
                pg_run(
                    installation,
                    "pg_ctl.exe",
                    "register",
                    "-N",
                    plan["name"],
                    "-D",
                    str(root / "data/postgres"),
                    "-U",
                    plan["account"],
                    "-S",
                    "demand",
                    "-w",
                    "-o",
                    plan["argv"][-1],
                )
                with scm.opened(plan["name"], mutate=True) as handle:
                    if not handle:
                        raise ValueError("E_NATIVE_SERVICE_MISSING")
                    scm.configure(handle, plan)
            else:
                scm.create(plan)
            intents[role] = (
                "bootstrap" if bootstrap and role == "postgres" else "registered"
            )
            installation.save()


def start_services(installation: Installation) -> None:
    root = installation.target
    with ServiceManager(writable=True) as scm:
        for role in ROLES:
            plan = plan_for(installation, role)
            with scm.opened(plan["name"], mutate=True) as handle:
                if not handle:
                    raise ValueError("E_NATIVE_SERVICE_MISSING")
                scm.activate(handle, plan)
                scm.start(handle, plan)
            if role == "postgres":
                # psql's guarded statement is idempotent; no password in arguments.
                pg_run(
                    installation,
                    "psql.exe",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(read_configuration(root)["ports"]["postgres"]),
                    "-U",
                    "kyrion",
                    "-d",
                    "postgres",
                    "--no-password",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-f",
                    str(root / "native-create-db.sql"),
                )
    config = read_configuration(root)
    if not all(healthy(root, role, config) for role in ("core", "web", "caddy")):
        raise ValueError("E_NATIVE_NOT_READY")
    installation.state["stage"] = "services-healthy"
    installation.save()


def stop_services(installation: Installation, remove=False) -> None:
    permissions(installation.target, "verify")
    with ServiceManager(writable=True) as scm:
        for role in reversed(ROLES):
            plan = plan_for(installation, role)
            with scm.opened(plan["name"], mutate=True) as handle:
                if handle:
                    if remove:
                        scm.remove(handle, plan)
                    else:
                        scm.stop(handle, plan)


def provision_native(
    target: Path,
    bundle: Path,
    public_key: Path,
    hostname: str,
    address: str,
    expected_manifest: str,
    worker: Path | None = None,
    ports: dict | None = None,
) -> dict:
    if os.name != "nt":
        raise ValueError("E_NATIVE_PLATFORM")
    preflight(target, hostname, address, fresh=not target.exists(), ports=ports)
    reviewed = authenticated_review(bundle, public_key)
    if reviewed.manifest["schemaVersion"] != 3:
        raise ValueError("E_NATIVE_SERVICE_HOST_REQUIRED")
    if reviewed.manifest_sha256 != expected_manifest:
        raise ValueError("E_REVIEW_CHANGED")
    if worker is None:
        if not getattr(sys, "frozen", False):
            raise ValueError("E_NATIVE_FROZEN_REQUIRED")
        worker = Path(sys.executable)
    if not worker.is_absolute() or not worker.is_file():
        raise ValueError("E_NATIVE_WORKER")
    service_plan(str(uuid.uuid4()), str(target), "core")
    with installation_lock(target):
        if target.exists():
            permissions(target, "root-only")
        installation = Installation(
            target,
            reviewed.manifest,
            expected_manifest,
            hostname,
            address,
            directory_factory=create_journalled_root,
        )
        if installation.state.get("backend") not in {None, "windows-native"}:
            raise ValueError("E_NATIVE_BACKEND")
        installation.state["backend"] = "windows-native"
        installation.save()
        try:
            installation.write("installer.exe", worker.read_bytes())
            installation.write(
                "native-manifest.json", json.dumps(reviewed.manifest, sort_keys=True)
            )
            permissions(target, "verify")
            private_bundle = stage_bundle(installation, bundle, public_key, reviewed)
            unpack(private_bundle, private_bundle / "public.pem", target / "payload")
            configure(installation, reviewed.manifest, expected_manifest, ports=ports)
            initialize_database(installation)
            register_services(installation)
            if installation.state.get("nativeAccessConfigured") is not True:
                permissions(target, "grant")
                installation.state["nativeAccessConfigured"] = True
                installation.save()
            start_services(installation)
            return installation.state
        except (OSError, ValueError, KeyError, TypeError) as error:
            code = str(error).split(":", 1)[0]
            installation.state["lastError"] = (
                code
                if code.startswith("E_") and code.replace("_", "").isalnum()
                else "E_NATIVE_OPERATION"
            )
            installation.save()
            raise


def repair_native(target: Path) -> dict:
    from recovery import load_installation

    with installation_lock(target):
        permissions(target, "verify")
        installation = load_installation(target)
        read_configuration(target)
        if installation.state.get("stage") == "uninstalled":
            raise ValueError("E_NATIVE_SIGNED_BUNDLE_REQUIRED")
        # Validate all existing definitions before stopping any component.
        with ServiceManager() as scm:
            for role in ROLES:
                plan = plan_for(installation, role)
                with scm.opened(plan["name"]) as handle:
                    if handle:
                        scm.assert_owned(handle, plan)
        stop_services(installation)
        register_services(installation, repair=True)
        permissions(target, "grant")
        start_services(installation)
        return {
            "stage": installation.state["stage"],
            "dataPreserved": True,
            "keysRotated": False,
            "autostartConfigured": True,
            "coldBootVerified": False,
        }


def uninstall_native(target: Path, purge: bool = False) -> dict:
    from recovery import load_installation

    if purge and Path(sys.executable).resolve().is_relative_to(target.resolve()):
        raise ValueError("E_NATIVE_USE_DOWNLOADED_INSTALLER")
    with installation_lock(target):
        permissions(target, "verify")
        installation = load_installation(target)
        # Inspect every definition before any service removal or filesystem change.
        with ServiceManager() as scm:
            for role in ROLES:
                plan = plan_for(installation, role)
                with scm.opened(plan["name"]) as handle:
                    if handle:
                        scm.assert_owned(handle, plan)
        stop_services(installation, remove=True)
        installation.state["stage"] = "uninstalled"
        installation.save()
        selected = target if purge else target / "payload"
        reject_links(selected)
        if selected.exists():
            for child in selected.rglob("*"):
                reject_links(child)
            # Exact reviewed owned path; shared runtimes/models are never selected.
            if (
                selected.resolve() != target.resolve()
                and not selected.resolve().is_relative_to(target.resolve())
            ):
                raise ValueError("E_NATIVE_CLEANUP_PATH")
            shutil.rmtree(selected)
        return {
            "runtimeRemoved": True,
            "dataRemoved": purge,
            "installerRetained": not purge,
            "sharedResourcesRemoved": False,
        }


def serve(target: Path, role: str) -> int:
    from native_roles import run_role
    from windows_host import dispatch

    path = target / "install-state.json"
    reject_links(path)
    if path.stat().st_size > 1024**2:
        raise ValueError("E_NATIVE_JOURNAL")
    state = json.loads(path.read_text(), object_pairs_hook=unique_object)
    runtime_config = json.loads((target / "native-runtime.json").read_text())
    plan = service_plan(
        state["installationId"], str(target), role, runtime_config["ports"]["postgres"]
    )
    if role == "postgres":
        raise ValueError("E_NATIVE_ROLE")

    def workload(stop, report):
        from windows_security import assert_identity

        assert_identity(plan["name"])
        permissions(target, "verify")
        with installation_lock(target / "data" / role / "worker"):
            run_role(target, role, stop, report)

    return dispatch(plan["name"], workload)
