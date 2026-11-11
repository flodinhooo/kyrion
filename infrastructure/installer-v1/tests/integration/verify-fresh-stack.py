"""Actual fresh Core/Web/TLS/bootstrap/offline-restart developer scenario.

Every resource has a new UUID and contains synthetic credentials only. Default:
internal network and no ports. Optional browser mode: separate bridge network
with only the disposable Caddy port bound to 127.0.0.1; it is not an offline test.
Neither mode establishes host boot acceptance.
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
from onboarding import CoreClient, CoreError
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


def main(images: dict[str, str], browser_checks: bool = False) -> None:
    if any(
        not re.fullmatch(r"sha256:[a-f0-9]{64}", image) for image in images.values()
    ):
        raise ValueError("E_IMAGE_PIN")
    images = {**images, "ha": images["helper"]}
    prefix = "kyrion-fresh-test-" + uuid.uuid4().hex
    containers, volumes = [], []
    network = None
    try:
        network = execute(
            [
                "docker",
                "network",
                "create",
                *([] if browser_checks else ["--internal"]),
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
os.chmod('/fixture/cert.pem',0o644)
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
        fixture_source = (
            Path(__file__).with_name("ha-fixture.py").read_text(encoding="utf-8")
        )
        ha = start(
            "ha",
            [
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--entrypoint",
                "python",
            ],
            ("-c", fixture_source),
        )
        ha_address = json.loads(execute(["docker", "inspect", ha]))[0][
            "NetworkSettings"
        ]["Networks"][prefix]["IPAddress"]
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
        caddy = start(
            "caddy",
            [
                *(["-p", "127.0.0.1::443"] if browser_checks else []),
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
                verify_selected_ha(client, ha, ha_address, real_run)
                if browser_checks:
                    real_run(
                        [
                            "docker",
                            "exec",
                            ha,
                            "curl",
                            "--fail",
                            "--silent",
                            "-X",
                            "POST",
                            "http://127.0.0.1:8123/fixture/reset",
                        ],
                        capture_output=True,
                        check=True,
                        timeout=15,
                    )
                    bindings = json.loads(execute_inspect(caddy, real_run))[0][
                        "NetworkSettings"
                    ]["Ports"]["443/tcp"]
                    if len(bindings) != 1 or bindings[0]["HostIp"] != "127.0.0.1":
                        raise ValueError("E_BROWSER_FIXTURE_BINDING")
                    checked = real_run(
                        [
                            "node",
                            str(Path(__file__).with_name("verify-ha-browser.mjs")),
                        ],
                        input=json.dumps(
                            {
                                "webUrl": "https://fixture.test:"
                                + bindings[0]["HostPort"],
                                "session": client.session,
                            }
                        ),
                        capture_output=True,
                        text=True,
                        timeout=180,
                        check=False,
                    )
                    if checked.returncode:
                        raise ValueError("E_HA_BROWSER: " + checked.stdout[-1500:])
                    effect = real_run(
                        [
                            "docker",
                            "exec",
                            ha,
                            "curl",
                            "--fail",
                            "--silent",
                            "http://127.0.0.1:8123/fixture/status",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=15,
                    )
                    if json.loads(effect.stdout)["posts"] != 0:
                        raise ValueError("E_HA_BROWSER_SAVE_SWITCHED_DEVICE")
                    print(checked.stdout.strip())
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
            bindings = inspected["HostConfig"].get("PortBindings")
            if bindings and not (
                browser_checks
                and container == caddy
                and all(
                    row["HostIp"] == "127.0.0.1"
                    for rows in bindings.values()
                    for row in rows
                )
            ):
                raise ValueError("E_FIXTURE_EXPOSURE")
        print(
            json.dumps(
                {
                    "freshBootstrap": True,
                    "trustedTlsLogin": True,
                    "ownerAndSpaceCreatedByCore": True,
                    "localLoginAfterCoreAndDatabaseRestart": True,
                    "bootstrapRemainsClosed": True,
                    "publishedPorts": ["127.0.0.1 ephemeral browser fixture"]
                    if browser_checks
                    else [],
                    "network": "bridge-loopback-browser-fixture"
                    if browser_checks
                    else "internal",
                    "aiHardwareMicConfigured": False,
                    "hostBootAccepted": False,
                    "productionDataUsed": False,
                    "homeAssistantSelectedControl": "synthetic-provider-only",
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


def execute_inspect(container: str, runner) -> str:
    return runner(
        ["docker", "inspect", container],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout


def verify_selected_ha(
    client: CoreClient, fixture: str, address: str, docker_run
) -> None:
    def check(condition, code):
        if not condition:
            raise ValueError(code)

    def fixture_request(path, method="GET"):
        response = docker_run(
            [
                "docker",
                "exec",
                fixture,
                "curl",
                "--fail",
                "--silent",
                "--max-time",
                "5",
                "-X",
                method,
                "http://127.0.0.1:8123" + path,
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        return json.loads(response.stdout)

    credentials = {
        "baseUrl": "http://" + address + ":8123",
        "accessToken": "synthetic-ha-fixture",
    }
    base = "/v1/integrations/home-assistant"
    preview = client.request("POST", base + "/preview", credentials)
    check(len(preview["devices"]) == 2, "E_HA_FIXTURE_PREVIEW")
    source = next(row for row in preview["devices"] if row["name"] == "Synthetic a")
    entity = next(row for row in source["entities"] if row["name"] == "fixture")
    choice = {
        "key": source["key"],
        "entityKeys": [entity["key"]],
        "allowControl": True,
        "overrideRoom": True,
        "roomId": None,
    }
    body = {**credentials, "expectedRevision": preview["revision"], "devices": [choice]}
    result = client.request("POST", base + "/selection", body)
    check(result["imported"] == 1 and result["reason"] is None, "E_HA_FIXTURE_IMPORT")
    try:
        client.request("POST", base + "/selection", body)
    except CoreError as failure:
        check(
            failure.status == 409 and failure.code == "selection_conflict",
            "E_HA_WRONG_CONFLICT",
        )
    else:
        raise ValueError("E_HA_STALE_REVISION_ACCEPTED")
    devices = client.request("GET", "/v1/devices")
    selected = [device for device in devices if device["provider"] == "home_assistant"]
    check(len(selected) == 1, "E_HA_UNSELECTED_VISIBLE")
    device = selected[0]
    check(
        device["room"] is None and device["state"]["temperatureCelsius"] is None,
        "E_HA_UNSELECTED_ENTITY_IMPORTED",
    )
    check(
        any(capability["id"] == "power.set" for capability in device["capabilities"]),
        "E_HA_CONTROL_CONSENT_MISSING",
    )
    status = fixture_request("/fixture/status")
    check(status["posts"] == 0, "E_HA_SAVE_SWITCHED_DEVICE")
    command = {
        "capability": "power.set",
        "selector": {"provider": "home_assistant", "deviceId": device["id"]},
        "arguments": {"on": True},
    }
    action = client.request("POST", "/v1/device-commands", command)
    check(action["succeeded"] == 1 and action["failed"] == 0, "E_HA_FIXTURE_CONTROL")
    fixture_request("/fixture/remove", "POST")
    client.request("POST", base + "/sync")
    missing = next(
        row for row in client.request("GET", "/v1/devices") if row["id"] == device["id"]
    )
    check(
        missing["availability"] == "unknown"
        and not any(cap["id"] == "power.set" for cap in missing["capabilities"]),
        "E_HA_REMOVED_ENTITY_ACTIVE",
    )
    client.request(
        "POST",
        base + "/selection",
        {"expectedRevision": result["revision"], "devices": []},
    )
    check(
        not any(
            row["provider"] == "home_assistant"
            for row in client.request("GET", "/v1/devices")
        ),
        "E_HA_DESELECTION_IGNORED",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-checks", action="store_true")
    for name in ("core", "web", "postgres", "caddy", "helper"):
        parser.add_argument("--" + name + "-image", required=True)
    arguments = vars(parser.parse_args())
    main(
        {
            name: arguments[name + "_image"]
            for name in ("core", "web", "postgres", "caddy", "helper")
        },
        arguments["browser_checks"],
    )
