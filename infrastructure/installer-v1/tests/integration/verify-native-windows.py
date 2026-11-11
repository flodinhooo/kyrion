"""Real native Windows component integration, with synthetic loopback-only data.

No services/tasks are registered. This proves process integration, not machine
startup, Local Service ACLs, network isolation, or production installation.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import native_bundle


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main(bundle: Path, key: Path, payload: Path, work_parent: Path) -> dict:
    if os.name != "nt":
        raise ValueError("E_WINDOWS_FIXTURE_PLATFORM")
    # Authenticate and verify every actual executable before starting anything.
    native_bundle.unpack(bundle, key, payload)
    runtime = payload / "runtime"
    environment = {
        name: os.environ[name]
        for name in ("SystemRoot", "WINDIR", "SystemDrive", "TEMP", "TMP", "COMSPEC")
        if name in os.environ
    }
    environment["PATH"] = (
        str(runtime / "postgres/bin")
        + ";"
        + str(Path(os.environ["SystemRoot"]) / "System32")
    )
    environment["JAVA_TOOL_OPTIONS"] = ""
    environment["NODE_OPTIONS"] = ""
    # Suppress native missing-DLL GUI dialogs only in this developer process.
    import ctypes

    ctypes.windll.kernel32.SetErrorMode(0x8003)
    ports = []
    while len(ports) < 4:
        value = free_port()
        if value not in ports:
            ports.append(value)
    pg_port, core_port, web_port, tls_port = ports
    processes = []
    handles = []
    opener = build_opener(ProxyHandler({}))

    def request(method, route, body=None, token=None, bootstrap=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if bootstrap:
            headers["X-Kyrion-Setup-Secret"] = bootstrap
        req = Request(
            "http://127.0.0.1:" + str(core_port) + route,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        with opener.open(req, timeout=5) as response:
            data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise ValueError("E_NATIVE_FIXTURE_RESPONSE")
            return json.loads(data) if data else None

    with tempfile.TemporaryDirectory(
        prefix="kyrion-native-stack-", dir=work_parent
    ) as directory:
        root = Path(directory)
        environment.update(
            APPDATA=str(root / "appdata"),
            LOCALAPPDATA=str(root / "localappdata"),
            HOME=str(root),
            USERPROFILE=str(root),
        )
        for name in ("appdata", "localappdata", "knowledge"):
            (root / name).mkdir()
        password = secrets.token_urlsafe(32)
        bootstrap = secrets.token_urlsafe(32)
        for name, value in {
            "pg-password": password,
            "bootstrap": bootstrap,
            "credential": secrets.token_hex(32),
            "audit": secrets.token_hex(32),
        }.items():
            (root / name).write_bytes(
                bytes.fromhex(value)
                if name in {"credential", "audit"}
                else value.encode("utf-8")
            )
        pg = runtime / "postgres/bin"
        data = root / "postgres"
        pg_started = False

        def run(arguments, **kwargs):
            # Daemon-launch helpers may leave inherited pipe handles in children.
            # File output avoids waiting for unrelated pipe EOF after helper exit.
            with (root / "commands.log").open("ab") as output:
                return subprocess.run(
                    [str(x) for x in arguments],
                    cwd=root,
                    env=environment,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=90,
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    **kwargs,
                )

        def start(arguments, name, extra=None):
            output = (root / (name + ".log")).open("wb")
            handles.append(output)
            process = subprocess.Popen(
                [str(x) for x in arguments],
                cwd=root,
                env={**environment, **(extra or {})},
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            processes.append(process)
            return process

        def stop(process):
            if process.poll() is None:
                # Only the exact PID created by this fixture and its descendants.
                subprocess.run(
                    [
                        str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    capture_output=True,
                    timeout=20,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                process.wait(timeout=20)

        def wait_core():
            for _ in range(120):
                if core.poll() is not None:
                    raise ValueError("E_NATIVE_FIXTURE_CORE_EXIT")
                try:
                    if request("GET", "/actuator/health").get("status") == "UP":
                        return
                except (URLError, HTTPError, TimeoutError, OSError):
                    pass
                time.sleep(1)
            raise ValueError("E_NATIVE_FIXTURE_CORE_READY")

        try:
            run(
                [
                    pg / "initdb.exe",
                    "-D",
                    data,
                    "-U",
                    "kyrion",
                    "--pwfile=" + str(root / "pg-password"),
                    "--auth=scram-sha-256",
                    "--encoding=UTF8",
                    "--locale=C",
                ]
            )
            with (data / "postgresql.conf").open("a") as stream:
                stream.write(
                    "\nlisten_addresses='127.0.0.1'\nport=" + str(pg_port) + "\n"
                )
            pg_started = True  # Cleanup also covers a timeout after daemon startup.
            run(
                [
                    pg / "pg_ctl.exe",
                    "start",
                    "-D",
                    data,
                    "-l",
                    root / "postgres.log",
                    "-w",
                ]
            )
            pg_started = True
            environment["PGPASSFILE"] = str(root / "pgpass")
            (root / "pgpass").write_text(
                "127.0.0.1:" + str(pg_port) + ":*:kyrion:" + password + "\n"
            )
            run(
                [
                    pg / "createdb.exe",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(pg_port),
                    "-U",
                    "kyrion",
                    "--no-password",
                    "kyrion",
                ]
            )
            core_environment = {
                "SERVER_PORT": str(core_port),
                "SPRING_CONFIG_IMPORT": "",
                "KYRION_CORE_ADDRESS": "127.0.0.1",
                "KYRION_DATABASE_URL": "jdbc:postgresql://127.0.0.1:"
                + str(pg_port)
                + "/kyrion",
                "KYRION_DATABASE_USER": "kyrion",
                "KYRION_DATABASE_PASSWORD_FILE": str(root / "pg-password"),
                "KYRION_BOOTSTRAP_SECRET_FILE": str(root / "bootstrap"),
                "KYRION_CREDENTIAL_KEY_FILE": str(root / "credential"),
                "KYRION_AUDIT_INTEGRITY_KEY_FILE": str(root / "audit"),
                "KYRION_KNOWLEDGE_ROOT": str(root / "knowledge"),
                "KYRION_KNOWLEDGE_PARSER_JAR": str(
                    payload / "app/core/knowledge-parser.jar"
                ),
                "KYRION_AI_BASE_URL": "http://127.0.0.1:9",
                "KYRION_KNOWLEDGE_EMBEDDING_URL": "http://127.0.0.1:9",
                "KYRION_AI_CLOUD_ENABLED": "false",
                "KYRION_CENTRAL_ENABLED": "false",
            }
            core_command = [
                runtime / "java/bin/java.exe",
                "-jar",
                payload / "app/core/core-runtime.jar",
            ]
            core = start(core_command, "core", core_environment)
            wait_core()
            if request("GET", "/v1/auth/setup/status")["setupRequired"] is not True:
                raise ValueError("E_NATIVE_FIXTURE_NOT_FRESH")
            credentials = {
                "username": "fixture-owner",
                "password": "Synthetic-local-password-123456",
            }
            response = request(
                "POST",
                "/v1/auth/setup",
                {
                    **credentials,
                    "spaceType": "HOME",
                    "spaceName": "Native developer fixture",
                },
                bootstrap=bootstrap,
            )
            token = response["sessionToken"]
            if "OWNER" not in request("GET", "/v1/auth/me", token=token)["roles"]:
                raise ValueError("E_NATIVE_FIXTURE_OWNER")
            request("GET", "/v1/space", token=token)
            request("GET", "/v1/devices", token=token)
            web = start(
                [runtime / "node/node.exe", payload / "app/web/server.js"],
                "web",
                {
                    "HOSTNAME": "127.0.0.1",
                    "PORT": str(web_port),
                    "CORE_SERVICE_URL": "http://127.0.0.1:" + str(core_port),
                    "KYRION_PUBLIC_URL": "https://localhost:" + str(tls_port),
                    "NEXT_TELEMETRY_DISABLED": "1",
                },
            )
            openssl = shutil.which("openssl")
            if not openssl:
                raise ValueError("E_NATIVE_FIXTURE_OPENSSL")
            run(
                [
                    openssl,
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                    "-addext",
                    "subjectAltName=DNS:localhost",
                    "-keyout",
                    root / "tls.key",
                    "-out",
                    root / "tls.crt",
                ]
            )
            (root / "Caddyfile").write_text(
                """{
    admin off
    persist_config off
    auto_https off
}
https://localhost:PORT {
    bind 127.0.0.1
    tls "CERT" "KEY"
    reverse_proxy 127.0.0.1:WEB
}
""".replace("PORT", str(tls_port))
                .replace("WEB", str(web_port))
                .replace("CERT", (root / "tls.crt").as_posix())
                .replace("KEY", (root / "tls.key").as_posix())
            )
            caddy = start(
                [
                    runtime / "caddy/caddy.exe",
                    "run",
                    "--config",
                    root / "Caddyfile",
                    "--adapter",
                    "caddyfile",
                ],
                "caddy",
            )
            import urllib.request

            trusted = urllib.request.build_opener(
                ProxyHandler({}),
                urllib.request.HTTPSHandler(
                    context=ssl.create_default_context(cafile=str(root / "tls.crt"))
                ),
            )
            for _ in range(60):
                try:
                    with trusted.open(
                        "https://localhost:" + str(tls_port) + "/login", timeout=5
                    ) as page:
                        if b"<html" in page.read(2 * 1024 * 1024).lower():
                            break
                except (URLError, HTTPError, TimeoutError, OSError):
                    pass
                if web.poll() is not None or caddy.poll() is not None:
                    raise ValueError("E_NATIVE_FIXTURE_FRONTEND_EXIT")
                time.sleep(1)
            else:
                raise ValueError("E_NATIVE_FIXTURE_TLS_WEB")
            stop(core)
            run(
                [
                    pg / "pg_ctl.exe",
                    "restart",
                    "-D",
                    data,
                    "-m",
                    "fast",
                    "-l",
                    root / "postgres.log",
                    "-w",
                ]
            )
            core = start(core_command, "core-restarted", core_environment)
            wait_core()
            token = request("POST", "/v1/auth/login", credentials)["sessionToken"]
            if "OWNER" not in request("GET", "/v1/auth/me", token=token)["roles"]:
                raise ValueError("E_NATIVE_FIXTURE_RESTART_LOGIN")
            if request("GET", "/v1/auth/setup/status")["setupRequired"] is not False:
                raise ValueError("E_NATIVE_FIXTURE_BOOTSTRAP_REOPENED")
            return {
                "nativeProcesses": True,
                "freshDatabase": True,
                "coreMigrations": True,
                "ownerAndSpaceCreated": True,
                "trustedTlsWeb": True,
                "processRestartLogin": True,
                "bootstrapRemainsClosed": True,
                "servicesOrTasksRegistered": False,
                "coldBootAccepted": False,
                "networkIsolated": False,
            }
        except BaseException:
            failure = work_parent / ("native-fixture-failure-" + root.name)
            failure.mkdir()
            # Synthetic developer logs only; never copy password/key/config files.
            for log in root.glob("*.log"):
                shutil.copyfile(log, failure / log.name)
            raise
        finally:
            for process in reversed(processes):
                stop(process)
            if pg_started:
                status = subprocess.run(
                    [str(pg / "pg_ctl.exe"), "status", "-D", str(data)],
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    timeout=20,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if status.returncode == 0:
                    run([pg / "pg_ctl.exe", "stop", "-D", data, "-m", "fast", "-w"])
                elif status.returncode != 3:
                    raise ValueError("E_NATIVE_FIXTURE_POSTGRES_CLEANUP")
            for handle in handles:
                handle.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "key", "payload", "work-parent", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = main(
        args.bundle.resolve(),
        args.key.resolve(),
        args.payload.resolve(),
        args.work_parent.resolve(),
    )
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
