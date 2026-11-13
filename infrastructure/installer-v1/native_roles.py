"""Fixed native role commands/environment, integrity and real readiness."""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

from bundle import sha256, unique_object
from host import reject_links
from runtime import atomic_json, validate_network
from windows_process import ContainedProcess
from windows_system import base_environment


def validate_ports(ports: dict) -> dict:
    if (
        not isinstance(ports, dict)
        or set(ports) != {"postgres", "core", "web", "caddy"}
        or any(
            type(value) is not int
            or not (1 if role == "caddy" else 1024) <= value <= 65535
            for role, value in ports.items()
        )
        or len(set(ports.values())) != 4
    ):
        raise ValueError("E_NATIVE_PORTS")
    return ports.copy()


def read_configuration(root: Path) -> dict:
    reject_links(root)
    if not root.is_absolute():
        raise ValueError("E_NATIVE_TARGET")
    journal = root / "install-state.json"
    if not journal.is_file() or journal.stat().st_size > 1024**2:
        raise ValueError("E_NATIVE_JOURNAL")
    state = json.loads(
        journal.read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )
    if (
        state.get("backend") != "windows-native"
        or state.get("rootPath") != str(root.resolve())
        or not isinstance(state.get("files"), dict)
    ):
        raise ValueError("E_NATIVE_JOURNAL")
    for name in ("installer.exe", "native-runtime.json", "native-manifest.json"):
        path = root / name
        reject_links(path)
        if not path.is_file() or sha256(path) != state["files"].get(name):
            raise ValueError("E_NATIVE_INTEGRITY")
    if (root / "identity-provider.json").exists() and sha256(
        root / "identity-provider.json"
    ) != state["files"].get("identity-provider.json"):
        raise ValueError("E_NATIVE_INTEGRITY")
    if (root / "native-runtime.json").stat().st_size > 16384:
        raise ValueError("E_NATIVE_CONFIGURATION")
    config = json.loads(
        (root / "native-runtime.json").read_text(), object_pairs_hook=unique_object
    )
    validate_network(config["hostname"], config["address"], allow_loopback=True)
    if (
        set(config) != {"formatVersion", "hostname", "address", "ports"}
        or type(config["formatVersion"]) is not int
        or config["formatVersion"] != 1
        or config["hostname"] != state["configuration"]["hostname"]
        or config["address"] != state["configuration"]["address"]
    ):
        raise ValueError("E_NATIVE_CONFIGURATION")
    validate_ports(config["ports"])
    return config


def role_plan(
    root: Path, role: str, config: dict
) -> tuple[Path, list[str], dict[str, str]]:
    if role not in {"core", "web", "caddy"}:
        raise ValueError("E_NATIVE_ROLE")
    payload = root / "payload"
    runtime = payload / "runtime"
    data = root / "data" / role
    environment = base_environment()
    environment.update(
        PATH=str(runtime / "java/bin") + ";" + base_environment()["PATH"],
        TEMP=str(data / "temp"),
        TMP=str(data / "temp"),
        HOME=str(data),
        USERPROFILE=str(data),
        APPDATA=str(data / "appdata"),
        LOCALAPPDATA=str(data / "localappdata"),
        JAVA_TOOL_OPTIONS="",
        JDK_JAVA_OPTIONS="",
        _JAVA_OPTIONS="",
        NODE_OPTIONS="",
    )
    ports = config["ports"]
    if role == "core":
        environment.update(
            SERVER_PORT=str(ports["core"]),
            SERVER_SSL_ENABLED="true",
            SERVER_SSL_CERTIFICATE=(root / "core-cert.pem").as_uri(),
            SERVER_SSL_CERTIFICATE_PRIVATE_KEY=(root / "secrets/core-tls.key").as_uri(),
            SPRING_CONFIG_IMPORT="",
            KYRION_CORE_ADDRESS="127.0.0.1",
            KYRION_DATABASE_URL="jdbc:postgresql://127.0.0.1:"
            + str(ports["postgres"])
            + "/kyrion",
            KYRION_DATABASE_USER="kyrion",
            KYRION_DATABASE_PASSWORD_FILE=str(root / "secrets/postgres-password"),
            KYRION_BOOTSTRAP_SECRET_FILE=str(root / "secrets/bootstrap.secret"),
            KYRION_CREDENTIAL_KEY_FILE=str(root / "secrets/credential.key"),
            KYRION_AUDIT_INTEGRITY_KEY_FILE=str(root / "secrets/audit-integrity.key"),
            KYRION_KNOWLEDGE_ROOT=str(root / "data/knowledge"),
            KYRION_KNOWLEDGE_PARSER_JAR=str(payload / "app/core/knowledge-parser.jar"),
            KYRION_AI_BASE_URL="http://127.0.0.1:9",
            KYRION_KNOWLEDGE_EMBEDDING_URL="http://127.0.0.1:9",
            KYRION_AI_CLOUD_ENABLED="false",
            KYRION_CENTRAL_ENABLED="false",
        )
        identity_file = root / "identity-provider.json"
        if identity_file.exists():
            from identity_settings import validate_identity

            if identity_file.stat().st_size > 4096:
                raise ValueError("E_IDENTITY_CONFIG")
            identity = validate_identity(json.loads(identity_file.read_text()))
            environment.update(
                KYRION_CENTRAL_ENABLED="true",
                KYRION_CENTRAL_ISSUER=identity["issuer"],
                KYRION_CENTRAL_CLIENT_ID=identity["clientId"],
                KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP=str(
                    identity["allowLoopbackHttp"]
                ).lower(),
            )
        return (
            runtime / "java/bin/java.exe",
            ["-jar", str(payload / "app/core/core-runtime.jar")],
            environment,
        )
    if role == "web":
        environment.update(
            HOSTNAME="127.0.0.1",
            PORT=str(ports["web"]),
            CORE_SERVICE_URL="https://127.0.0.1:" + str(ports["core"]),
            NODE_EXTRA_CA_CERTS=str(root / "core-cert.pem"),
            KYRION_PUBLIC_URL="https://"
            + config["hostname"]
            + (":" + str(ports["caddy"]) if ports["caddy"] != 443 else ""),
            NEXT_TELEMETRY_DISABLED="1",
        )
        return (
            runtime / "node/node.exe",
            [str(payload / "app/web/server.js")],
            environment,
        )
    return (
        runtime / "caddy/caddy.exe",
        ["run", "--config", str(root / "data/Caddyfile"), "--adapter", "caddyfile"],
        environment,
    )


def healthy(root: Path, role: str, config: dict) -> bool:
    try:
        if role == "caddy":
            context = ssl.create_default_context(cafile=str(root / "data/tls/cert.pem"))
            with (
                socket.create_connection(
                    (config["address"], config["ports"]["caddy"]), timeout=2
                ) as connection,
                context.wrap_socket(
                    connection, server_hostname=config["hostname"]
                ) as secured,
            ):
                secured.sendall(
                    (
                        "GET /login HTTP/1.1\r\nHost: "
                        + config["hostname"]
                        + "\r\nConnection: close\r\n\r\n"
                    ).encode("ascii")
                )
                response = http.client.HTTPResponse(secured)
                response.begin()
                return (
                    response.status == 200
                    and b"<html" in response.read(2 * 1024**2).lower()
                )
        route = "/actuator/health" if role == "core" else "/login"
        handlers = [ProxyHandler({})]
        if role in {"core", "web"}:
            handlers.append(
                HTTPSHandler(
                    context=ssl.create_default_context(
                        cafile=str(root / (role + "-cert.pem"))
                    )
                )
            )
        with build_opener(*handlers).open(
            "https://127.0.0.1:" + str(config["ports"][role]) + route, timeout=2
        ) as response:
            value = response.read(2 * 1024**2)
            return (
                (json.loads(value).get("status") == "UP")
                if role == "core"
                else b"<html" in value.lower()
            )
    except (OSError, ValueError, http.client.HTTPException):
        return False


def initialize_postgres(root: Path, stop, report) -> None:
    config = read_configuration(root)
    state = json.loads(
        (root / "install-state.json").read_text(), object_pairs_hook=unique_object
    )
    pending = state.get("nativeDatabasePending")
    import uuid

    if (
        not isinstance(pending, str)
        or not pending.startswith("postgres-pending-")
        or str(uuid.UUID(pending[17:])) != pending[17:]
    ):
        raise ValueError("E_NATIVE_DATABASE_STATE")
    directory = root / "data" / pending
    reject_links(directory)
    if not directory.is_dir() or any(directory.iterdir()):
        raise ValueError("E_NATIVE_EXISTING_DATABASE")
    data = root / "data/postgres-init"
    for leaf in ("temp", "appdata", "localappdata"):
        (data / leaf).mkdir(exist_ok=True)
    _, _, environment = role_plan(root, "core", config)
    for key in list(environment):
        if key.startswith("KYRION_"):
            del environment[key]
    environment.update(
        TEMP=str(data / "temp"),
        TMP=str(data / "temp"),
        HOME=str(data),
        USERPROFILE=str(data),
        APPDATA=str(data / "appdata"),
        LOCALAPPDATA=str(data / "localappdata"),
    )
    executable = root / "payload/runtime/postgres/bin/initdb.exe"
    from windows_security import check_access

    check_access(root, "postgres-init", executable)
    arguments = [
        "-D",
        str(directory),
        "-U",
        "kyrion",
        "--pwfile=" + str(root / "secrets/postgres-password"),
        "--auth=scram-sha-256",
        "--encoding=UTF8",
        "--locale=C",
    ]
    with ContainedProcess(executable, arguments, environment, data) as child:
        report(4)
        deadline = time.monotonic() + 240
        while child.poll() is None:
            if stop.wait(0.2):
                return
            if time.monotonic() > deadline:
                raise ValueError("E_NATIVE_DATABASE_TIMEOUT")
        if child.poll() != 0:
            raise ValueError("E_NATIVE_DATABASE_INITIALIZATION")
    if (
        not (directory / "global/pg_control").is_file()
        or (directory / "PG_VERSION").read_text().strip() != "17"
    ):
        raise ValueError("E_NATIVE_DATABASE_INITIALIZATION")
    with (directory / "postgresql.conf").open("a") as stream:
        stream.write(
            "\nlisten_addresses='127.0.0.1'\nport="
            + str(config["ports"]["postgres"])
            + "\n"
        )
    atomic_json(data / "result.json", {"status": "initialized", "pending": pending})


def run_role(root: Path, role: str, stop, report) -> None:
    from authority import require_active

    config = read_configuration(root)
    require_active(
        json.loads(
            (root / "install-state.json").read_bytes(), object_pairs_hook=unique_object
        ),
        preparing=role == "postgres-init",
        migration=role == "core",
    )
    manifest_path = root / "native-manifest.json"
    if manifest_path.stat().st_size > 8 * 1024**2:
        raise ValueError("E_NATIVE_MANIFEST")
    manifest = json.loads(manifest_path.read_text(), object_pairs_hook=unique_object)
    prefixes = {
        "core": ("app/core/", "runtime/java/"),
        "web": ("app/web/", "runtime/node/"),
        "caddy": ("runtime/caddy/",),
        "postgres-init": ("runtime/postgres/",),
    }[role]
    last_report = time.monotonic()
    for item in manifest["files"]:
        if not item["path"].startswith((*prefixes, "runtime/installer/")):
            continue
        path = root / "payload" / item["path"]
        reject_links(path)
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            raise ValueError("E_NATIVE_INTEGRITY")
        if stop.is_set():
            return
        if time.monotonic() - last_report >= 2:
            report(2)
            last_report = time.monotonic()
    if role == "postgres-init":
        initialize_postgres(root, stop, report)
        return
    data = root / "data" / role
    for leaf in ("temp", "appdata", "localappdata"):
        (data / leaf).mkdir(exist_ok=True)
    executable, arguments, environment = role_plan(root, role, config)
    from windows_security import check_access

    check_access(root, role, executable)
    status = data / "service-status.json"
    if role == "web":
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            child_port = probe.getsockname()[1]
        environment["PORT"] = str(child_port)
    with ExitStack() as stack:
        child = stack.enter_context(
            ContainedProcess(executable, arguments, environment, data)
        )
        if role == "web":
            from native_web_transport import WebTransport

            stack.enter_context(
                WebTransport(root, config["ports"]["web"], child_port, child)
            )
        deadline = time.monotonic() + 120
        while not stop.is_set() and time.monotonic() < deadline:
            if child.poll() is not None:
                raise ValueError("E_NATIVE_CHILD_EXIT")
            if healthy(root, role, config):
                report(4)
                atomic_json(
                    status,
                    {
                        "state": "running",
                        "verified": True,
                        "secretBoundaryChecked": True,
                        "runtimeReadOnlyChecked": True,
                        "checkedAt": int(time.time()),
                    },
                )
                break
            report(2)
            stop.wait(2)
        else:
            if stop.is_set():
                return
            raise ValueError("E_NATIVE_NOT_READY")
        while not stop.wait(0.5):
            if child.poll() is not None:
                atomic_json(
                    status,
                    {
                        "state": "failed",
                        "code": "E_NATIVE_CHILD_EXIT",
                        "checkedAt": int(time.time()),
                    },
                )
                raise ValueError("E_NATIVE_CHILD_EXIT")
        report(3)
    atomic_json(status, {"state": "stopped", "checkedAt": int(time.time())})
