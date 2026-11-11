"""Actual fresh Core/Web/TLS/bootstrap/offline-restart developer scenario.

Every resource has a new UUID, uses a private internal Docker network, publishes
no port, and contains synthetic credentials only. This is not host boot acceptance.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from onboarding import CoreClient
from runtime import Installation, execute


def ready(container: str, postgres: bool = False) -> None:
    arguments = (
        ["pg_isready", "-U", "kyrion"]
        if postgres
        else [
            "curl",
            "--fail",
            "--silent",
            "--max-time",
            "5",
            "http://127.0.0.1:8080/actuator/health",
        ]
    )
    for _ in range(120):
        result = subprocess.run(
            ["docker", "exec", container, *arguments],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0 and (
            postgres or json.loads(result.stdout).get("status") == "UP"
        ):
            return
        time.sleep(1)
    raise ValueError("E_FIXTURE_NOT_READY")


def main(images: dict[str, str]) -> None:
    if any(
        not re.fullmatch(r"sha256:[a-f0-9]{64}", image) for image in images.values()
    ):
        raise ValueError("E_IMAGE_PIN")
    prefix = "kyrion-fresh-test-" + uuid.uuid4().hex
    containers, volumes = [], []
    network = None
    try:
        network = execute(
            [
                "docker",
                "network",
                "create",
                "--internal",
                "--label",
                "io.kyrion.test-fixture=true",
                prefix,
            ]
        ).strip()
        for kind in ("secrets", "postgres", "knowledge"):
            volumes.append(
                execute(
                    [
                        "docker",
                        "volume",
                        "create",
                        "--label",
                        "io.kyrion.test-fixture=true",
                        prefix + "-" + kind,
                    ]
                ).strip()
            )
        values = {
            "bootstrap.secret": secrets.token_urlsafe(32),
            "postgres-password": secrets.token_urlsafe(32),
            "credential.key": secrets.token_hex(32),
            "audit-integrity.key": secrets.token_hex(32),
        }
        script = """import json,os,subprocess,sys
from pathlib import Path
os.umask(0o077)
for name,value in json.load(sys.stdin).items():
 p=Path('/fixture')/name
 p.write_bytes(bytes.fromhex(value) if name.endswith('.key') else value.encode())
 os.chown(p,10001,10001)
os.chown('/knowledge',10001,10001)
subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=fixture.test','-addext','basicConstraints=critical,CA:FALSE','-addext','subjectAltName=DNS:fixture.test','-keyout','/fixture/key.pem','-out','/fixture/cert.pem'],capture_output=True,check=True)
os.chown('/fixture/cert.pem',10001,10001)
Path('/fixture/Caddyfile').write_text('{\\n admin off\\n persist_config off\\n}\\nhttps://fixture.test {\\n tls /fixture/cert.pem /fixture/key.pem\\n reverse_proxy web:3000\\n}\\n')
"""
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-i",
                "--mount",
                "type=volume,src=" + volumes[0] + ",dst=/fixture",
                "--mount",
                "type=volume,src=" + volumes[2] + ",dst=/knowledge",
                "--entrypoint",
                "python",
                images["helper"],
                "-c",
                script,
            ],
            input=json.dumps(values).encode(),
            capture_output=True,
            check=True,
            timeout=30,
        )

        def start(service, extra, command=()):
            container = execute(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    prefix + "-" + service,
                    "--network",
                    network,
                    "--network-alias",
                    service,
                    "--label",
                    "io.kyrion.test-fixture=true",
                    *extra,
                    images[service],
                    *command,
                ]
            ).strip()
            if not re.fullmatch(r"[a-f0-9]{64}", container):
                raise ValueError("E_FIXTURE_CONTAINER")
            containers.append(container)
            return container

        pg = start(
            "postgres",
            [
                "--mount",
                "type=volume,src=" + volumes[1] + ",dst=/var/lib/postgresql/data",
                "--mount",
                "type=volume,src=" + volumes[0] + ",dst=/run/secrets,readonly",
                "-e",
                "POSTGRES_USER=kyrion",
                "-e",
                "POSTGRES_DB=kyrion",
                "-e",
                "POSTGRES_PASSWORD_FILE=/run/secrets/postgres-password",
            ],
        )
        ready(pg, postgres=True)
        core = start(
            "core",
            [
                "--read-only",
                "--memory",
                "1536m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m",
                "--mount",
                "type=volume,src=" + volumes[0] + ",dst=/run/secrets,readonly",
                "--mount",
                "type=volume,src=" + volumes[2] + ",dst=/var/lib/kyrion/knowledge",
                "-e",
                "KYRION_CORE_ADDRESS=0.0.0.0",
                "-e",
                "KYRION_DATABASE_URL=jdbc:postgresql://postgres:5432/kyrion",
                "-e",
                "KYRION_DATABASE_USER=kyrion",
                "-e",
                "KYRION_DATABASE_PASSWORD_FILE=/run/secrets/postgres-password",
                "-e",
                "KYRION_CREDENTIAL_KEY_FILE=/run/secrets/credential.key",
                "-e",
                "KYRION_AUDIT_INTEGRITY_KEY_FILE=/run/secrets/audit-integrity.key",
                "-e",
                "KYRION_BOOTSTRAP_SECRET_FILE=/run/secrets/bootstrap.secret",
                "-e",
                "KYRION_CENTRAL_ENABLED=false",
                "-e",
                "KYRION_AI_CLOUD_ENABLED=false",
            ],
        )
        ready(core)
        start(
            "web",
            [
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m",
                "-e",
                "CORE_SERVICE_URL=http://core:8080",
                "-e",
                "KYRION_PUBLIC_URL=https://fixture.test",
            ],
        )
        start(
            "caddy",
            [
                "--network-alias",
                "fixture.test",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--cap-add",
                "NET_BIND_SERVICE",
                "--security-opt",
                "no-new-privileges:true",
                "--tmpfs",
                "/data:rw,nosuid,nodev,size=16m",
                "--tmpfs",
                "/config:rw,nosuid,nodev,size=16m",
                "--mount",
                "type=volume,src=" + volumes[0] + ",dst=/fixture,readonly",
                "--entrypoint",
                "caddy",
            ],
            ("run", "--config", "/fixture/Caddyfile", "--adapter", "caddyfile"),
        )
        for _ in range(60):
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    core,
                    "curl",
                    "--fail",
                    "--silent",
                    "--max-time",
                    "5",
                    "--cacert",
                    "/run/secrets/cert.pem",
                    "https://fixture.test/login",
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and b"<html" in result.stdout.lower():
                break
            time.sleep(1)
        else:
            raise ValueError("E_FIXTURE_TLS_LOGIN")
        real_run = subprocess.run

        def transport(arguments, **kwargs):
            if arguments[:2] != ["docker", "compose"]:
                raise ValueError("E_FIXTURE_TRANSPORT")
            return real_run(
                ["docker", "exec", "-i", core, "curl", "--config", "-"], **kwargs
            )

        with tempfile.TemporaryDirectory(prefix="kyrion-owner-fixture-") as directory:
            target = Path(directory) / "installation"
            installation = Installation(
                target,
                {"release": "1.0.0", "architecture": "linux/amd64"},
                "a" * 64,
                "fixture.test",
                "192.168.1.2",
            )
            installation.write("secrets/bootstrap.secret", values["bootstrap.secret"])
            client = CoreClient(installation)
            with patch("onboarding.subprocess.run", side_effect=transport):
                initial = client.request("GET", "/v1/auth/setup/status")
                if initial.get("setupRequired") is not True:
                    raise ValueError("E_FIXTURE_NOT_FRESH")
                user = client.login_or_setup(
                    "fixture-owner",
                    "Synthetic-local-password-123456",
                    "Isolated fixture",
                    "HOME",
                )
                if "OWNER" not in user.get("roles", []):
                    raise ValueError("E_FIXTURE_OWNER")
                space = client.request("GET", "/v1/space")
                client.request("GET", "/v1/devices")
                client.close()
            execute(["docker", "stop", core])
            execute(["docker", "restart", pg])
            ready(pg, postgres=True)
            execute(["docker", "start", core])
            ready(core)
            with patch("onboarding.subprocess.run", side_effect=transport):
                user = client.login_or_setup(
                    "fixture-owner", "Synthetic-local-password-123456"
                )
                restored = client.request("GET", "/v1/space")
                if (
                    restored["id"] != space["id"]
                    or restored["name"] != "Isolated fixture"
                ):
                    raise ValueError("E_FIXTURE_PERSISTENCE")
                if (
                    client.request("GET", "/v1/auth/setup/status").get("setupRequired")
                    is not False
                ):
                    raise ValueError("E_FIXTURE_BOOTSTRAP_REOPENED")
                client.close()
        for container in containers:
            inspected = json.loads(execute(["docker", "inspect", container]))[0]
            if inspected["HostConfig"].get("PortBindings"):
                raise ValueError("E_FIXTURE_EXPOSURE")
        print(
            json.dumps(
                {
                    "freshBootstrap": True,
                    "trustedTlsLogin": True,
                    "ownerAndSpaceCreatedByCore": True,
                    "localLoginAfterCoreAndDatabaseRestart": True,
                    "bootstrapRemainsClosed": True,
                    "publishedPorts": [],
                    "network": "internal",
                    "aiHardwareMicConfigured": False,
                    "hostBootAccepted": False,
                    "productionDataUsed": False,
                }
            )
        )
    finally:
        for container in reversed(containers):
            execute(["docker", "rm", "-f", "-v", container])
        if network:
            execute(["docker", "network", "rm", network])
        for volume in volumes:
            execute(["docker", "volume", "rm", volume])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("core", "web", "postgres", "caddy", "helper"):
        parser.add_argument("--" + name + "-image", required=True)
    arguments = vars(parser.parse_args())
    main(
        {
            name: arguments[name + "_image"]
            for name in ("core", "web", "postgres", "caddy", "helper")
        }
    )
