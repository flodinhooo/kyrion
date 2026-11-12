"""Real Linux Core/SQL/linked-account/HA acceptance in a pre-isolated netns.

Synthetic provider only. No Docker, systemd, host service changes or real devices.
Launch as an unprivileged test user after creating a namespace with only lo and
10.231.0.1/32. The runner refuses an externally connected network namespace.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import platform
import runpy
import secrets
import shlex
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from crypto_support import certificate, private_tls_key
from identity_fixture import IdentityFixture
from linked_onboarding import linked_setup
from onboarding import ROUTES, CoreClient, CoreError, guided_home_assistant


def isolated_namespace():
    if os.name != "posix" or os.geteuid() == 0:
        raise ValueError("E_FIXTURE_UNPRIVILEGED_LINUX_REQUIRED")
    result = subprocess.run(
        ["/usr/sbin/ip", "-json", "address"], capture_output=True, check=True, timeout=5
    )
    interfaces = json.loads(result.stdout)
    if len(interfaces) != 1 or interfaces[0]["ifname"] != "lo":
        raise ValueError("E_FIXTURE_NETWORK_NOT_ISOLATED")
    addresses = {item["local"] for item in interfaces[0]["addr_info"]}
    if not {"127.0.0.1", "10.231.0.1"} <= addresses:
        raise ValueError("E_FIXTURE_NETWORK_ADDRESS")


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def main(jar: Path, expected_digest: str, postgres: Path, work: Path, java: Path):
    isolated_namespace()
    digest = hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest != expected_digest:
        raise ValueError("E_FIXTURE_SOURCE_CHANGED")
    processes = []
    handles = []
    provider = None
    server = None
    pg_started = False
    with tempfile.TemporaryDirectory(
        prefix="kyrion-core-linux-", dir=work
    ) as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        (root / "secrets").mkdir(mode=0o700)
        (root / "knowledge").mkdir()
        password = secrets.token_urlsafe(32)
        local_password = "Synthetic-offline-password-123456"
        for name, material in {
            "pg-password": password.encode(),
            "secrets/bootstrap.secret": secrets.token_urlsafe(32).encode(),
            "credential": secrets.token_bytes(32),
            "audit": secrets.token_bytes(32),
            "core-tls.key": private_tls_key(),
        }.items():
            path = root / name
            path.write_bytes(material)
            path.chmod(0o600)
        (root / "core-cert.pem").write_bytes(
            certificate("localhost", "127.0.0.1", (root / "core-tls.key").read_bytes())
        )
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "HOME": str(root),
            "PGPASSWORD": password,
        }
        pg_port, core_port = free_port(), free_port()
        data = root / "postgres"
        opener = build_opener(
            ProxyHandler({}),
            HTTPSHandler(
                context=ssl.create_default_context(cafile=str(root / "core-cert.pem"))
            ),
        )

        def request(method, route, body=None, token=None, bootstrap=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            if bootstrap:
                headers["X-Kyrion-Setup-Secret"] = bootstrap
            req = Request(
                "https://127.0.0.1:" + str(core_port) + route,
                data=json.dumps(body).encode() if body is not None else None,
                headers=headers,
                method=method,
            )
            with opener.open(req, timeout=15) as response:
                raw = response.read(2 * 1024**2 + 1)
                if len(raw) > 2 * 1024**2:
                    raise ValueError("E_FIXTURE_RESPONSE_LIMIT")
                return json.loads(raw) if raw else None

        def run(arguments):
            with (root / "commands.log").open("ab") as log:
                subprocess.run(
                    [str(x) for x in arguments],
                    cwd=root,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    check=True,
                    timeout=90,
                )

        def start_core():
            log = (root / "core.log").open("ab")
            handles.append(log)
            child = subprocess.Popen(
                [str(java), "-jar", str(jar)],
                cwd=root,
                env={**environment, **core_environment},
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
            processes.append(child)
            for _ in range(120):
                if child.poll() is not None:
                    raise ValueError("E_FIXTURE_CORE_EXIT")
                try:
                    if request("GET", "/actuator/health").get("status") == "UP":
                        return child
                except (HTTPError, URLError, OSError, TimeoutError):
                    pass
                time.sleep(1)
            raise ValueError("E_FIXTURE_CORE_READY")

        def stop(child):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)

        def pg_start():
            run(
                [
                    postgres / "pg_ctl",
                    "-D",
                    data,
                    "-l",
                    root / "postgres.log",
                    "-o",
                    f"-h 127.0.0.1 -p {pg_port} -k {shlex.quote(str(root))}",
                    "-w",
                    "start",
                ]
            )

        def check(condition, code):
            if not condition:
                raise ValueError(code)

        def scalar(query):
            result = subprocess.run(
                [
                    str(postgres / "psql"),
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(pg_port),
                    "-U",
                    "kyrion",
                    "-d",
                    "kyrion",
                    "--no-password",
                    "-Atc",
                    query,
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            return result.stdout.strip()

        try:
            run(
                [
                    postgres / "initdb",
                    "-D",
                    data,
                    "-U",
                    "kyrion",
                    "--pwfile=" + str(root / "pg-password"),
                    "--auth=scram-sha-256",
                    "--no-locale",
                    "--encoding=UTF8",
                ]
            )
            pg_start()
            pg_started = True
            run(
                [
                    postgres / "createdb",
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
            provider = IdentityFixture(root)
            provider.start()
            core_environment = {
                "SERVER_PORT": str(core_port),
                "SERVER_SSL_ENABLED": "true",
                "SERVER_SSL_CERTIFICATE": (root / "core-cert.pem").as_uri(),
                "SERVER_SSL_CERTIFICATE_PRIVATE_KEY": (root / "core-tls.key").as_uri(),
                "SPRING_CONFIG_IMPORT": "",
                "KYRION_CORE_ADDRESS": "127.0.0.1",
                "KYRION_DATABASE_URL": f"jdbc:postgresql://127.0.0.1:{pg_port}/kyrion",
                "KYRION_DATABASE_USER": "kyrion",
                "KYRION_DATABASE_PASSWORD_FILE": str(root / "pg-password"),
                "KYRION_BOOTSTRAP_SECRET_FILE": str(root / "secrets/bootstrap.secret"),
                "KYRION_CREDENTIAL_KEY_FILE": str(root / "credential"),
                "KYRION_AUDIT_INTEGRITY_KEY_FILE": str(root / "audit"),
                "KYRION_KNOWLEDGE_ROOT": str(root / "knowledge"),
                "KYRION_AI_BASE_URL": "http://127.0.0.1:9",
                "KYRION_AI_CLOUD_ENABLED": "false",
                "KYRION_CENTRAL_ENABLED": "true",
                "KYRION_CENTRAL_ISSUER": provider.issuer,
                "KYRION_CENTRAL_CLIENT_ID": "kyrion-local",
                "KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP": "false",
                "JAVA_TOOL_OPTIONS": f"-Djavax.net.ssl.trustStore={provider.truststore} -Djavax.net.ssl.trustStoreType=PKCS12 -Djavax.net.ssl.trustStorePassword=isolated-test-store",
            }
            core = start_core()
            state = {}
            installation = SimpleNamespace(target=root, state=state, save=lambda: None)

            class Client(CoreClient):
                # Test-only direct TLS adapter. Production onboarding decisions
                # run unchanged; every reply comes from actual Core and SQL.
                def request(self, method, route, body=None, bootstrap=None):
                    if (method, route) not in ROUTES:
                        raise ValueError("E_API_ROUTE")
                    if route == "/v1/device-commands":
                        check(
                            fixture["state"]["posts"] == 0,
                            "E_FIXTURE_HA_SAVE_TRIGGERED_ACTION",
                        )
                    try:
                        return request(method, route, body, self.session, bootstrap)
                    except HTTPError as error:
                        raw = error.read(2 * 1024**2)
                        try:
                            code = json.loads(raw).get("code", "E_API")
                        except (ValueError, AttributeError):
                            code = "E_API"
                        raise CoreError(code, error.code) from None

            client = Client(installation)
            messages = json.loads((ROOT / "locales/en.json").read_text())
            provider.approved = True
            with (
                patch(
                    "builtins.input",
                    side_effect=[
                        "CHECK",
                        "fixture-owner",
                        "BUSINESS",
                        "Linux synthetic Space",
                        "USE",
                    ],
                ),
                patch("getpass.getpass", return_value=local_password),
                patch("builtins.print"),
            ):
                user = linked_setup(client, messages)
            check(state.get("centralIdentity") == "linked", "E_FIXTURE_LINKED_SETUP")
            owner = user["id"]
            space = request("GET", "/v1/space", token=client.session)
            fixture = runpy.run_path(str(Path(__file__).with_name("ha-fixture.py")))
            server = http.server.ThreadingHTTPServer(
                ("10.231.0.1", 0), fixture["Handler"]
            )
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            endpoint = "http://10.231.0.1:" + str(server.server_port)
            answers = [
                "CONFIGURE",
                endpoint,
                "1",
                "1",
                "ALLOW",
                "import",
                "IMPORT",
                "APPLY",
                "TEST",
                "1",
                "TURN-ON",
            ]
            with (
                patch("builtins.input", side_effect=answers),
                patch("getpass.getpass", return_value="synthetic-ha-fixture"),
                patch("builtins.print"),
            ):
                guided_home_assistant(client, messages)
            devices = client.request("GET", "/v1/devices")
            selected = [
                device for device in devices if device["provider"] == "home_assistant"
            ]
            check(len(selected) == 1, "E_FIXTURE_HA_SCOPE")
            device = selected[0]
            check(device["room"]["name"] == "Fixture room", "E_FIXTURE_HA_ROOM")
            check(
                device["state"]["on"] is True and fixture["state"]["posts"] == 1,
                "E_FIXTURE_HA_CONTROL",
            )
            check(
                device["state"]["temperatureCelsius"] is None,
                "E_FIXTURE_HA_ENTITY_SCOPE",
            )
            fixture["state"]["on"] = False
            refresh_started = time.monotonic()
            # The 30s scheduled scan also respects the 30s per-owner throttle;
            # a selection between scans can therefore need the following scan.
            for _ in range(75):
                # Read SQL directly: GET /devices can trigger an on-demand
                # refresh and would not prove that the scheduler ran itself.
                identity = str(uuid.UUID(device["id"]))
                if (
                    scalar(
                        f"SELECT on_state FROM home_assistant_device WHERE connection_id='{identity}'"
                    )
                    == "f"
                ):
                    break
                time.sleep(1)
            else:
                raise ValueError("E_FIXTURE_HA_BACKGROUND_REFRESH")
            refresh_elapsed = round(time.monotonic() - refresh_started, 1)
            check(
                next(
                    row
                    for row in client.request("GET", "/v1/devices")
                    if row["id"] == device["id"]
                )["state"]["on"]
                is False,
                "E_FIXTURE_HA_REFRESH_NOT_VISIBLE",
            )
            check(fixture["state"]["posts"] == 1, "E_FIXTURE_HA_UNREQUESTED_ACTION")
            fixture["state"]["removed"] = True
            client.request("POST", "/v1/integrations/home-assistant/sync")
            missing = next(
                row
                for row in client.request("GET", "/v1/devices")
                if row["id"] == device["id"]
            )
            check(
                missing["availability"] == "unknown"
                and not any(
                    cap["id"] == "power.set" for cap in missing["capabilities"]
                ),
                "E_FIXTURE_HA_REMOVAL",
            )
            client.request("DELETE", "/v1/integrations/home-assistant")
            check(
                client.request("GET", "/v1/integrations/home-assistant")["configured"]
                is False,
                "E_FIXTURE_HA_DISCONNECT",
            )
            check(
                not any(
                    row["provider"] == "home_assistant"
                    for row in client.request("GET", "/v1/devices")
                ),
                "E_FIXTURE_HA_DISCONNECTED_CATALOG",
            )
            client.close()
            provider.stop()
            stop(core)
            run([postgres / "pg_ctl", "-D", data, "-m", "fast", "-w", "stop"])
            pg_started = False
            pg_start()
            pg_started = True
            core = start_core()
            client = Client(installation)
            restored = client.login_or_setup("fixture-owner", local_password)
            # The normal linked flow requested the username before password.
            check(restored["id"] == owner, "E_FIXTURE_OFFLINE_IDENTITY")
            check(
                client.request("GET", "/v1/space")["id"] == space["id"],
                "E_FIXTURE_OFFLINE_SPACE",
            )
            client.close()
            return {
                "coreJarSha256": digest,
                "observedSchema": int(
                    scalar(
                        "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'"
                    )
                ),
                "architecture": platform.machine(),
                "realLinuxCorePostgres": True,
                "networkNamespaceIsolated": True,
                "syntheticOidcTlsVerified": True,
                "linkedBusinessOwner": True,
                "homeAssistantSyntheticOnly": True,
                "selectedEntityAndRoomImport": True,
                "oneDeliberateSyntheticAction": True,
                "scheduledStateRefresh": True,
                "scheduledRefreshObservedSeconds": refresh_elapsed,
                "removedEntityUnavailable": True,
                "disconnectTokenAndSelection": True,
                "offlineIdentityAfterProcessRestart": True,
                "hostBootAccepted": False,
                "realHouseholdActions": False,
            }
        finally:
            for child in reversed(processes):
                stop(child)
            if server is not None:
                server.shutdown()
                server.server_close()
            if provider is not None and not provider.closed:
                provider.stop()
            if pg_started:
                run([postgres / "pg_ctl", "-D", data, "-m", "immediate", "-w", "stop"])
            for handle in handles:
                handle.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-jar", type=Path, required=True)
    parser.add_argument("--core-sha256", required=True)
    parser.add_argument("--java", type=Path, default=Path("/usr/bin/java"))
    parser.add_argument(
        "--postgres-bin", type=Path, default=Path("/usr/lib/postgresql/17/bin")
    )
    parser.add_argument("--work-parent", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = main(
        args.core_jar.resolve(),
        args.core_sha256,
        args.postgres_bin.resolve(),
        args.work_parent.resolve(),
        args.java.resolve(),
    )
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
