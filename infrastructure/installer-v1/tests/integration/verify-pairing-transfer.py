"""Real owner/Core/Caddy pairing export and native-target import in an isolated LAN."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import runpy
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from crypto_support import certificate, private_tls_key
from device_management import guided_devices
from node_pairing import export, load
from node_transport import agent_handle
from postgres_fixture import PostgresFixture


@contextlib.contextmanager
def proxy(args, installation, core):
    if hashlib.sha256(args.caddy.read_bytes()).hexdigest() != args.caddy_sha256:
        raise ValueError("E_FIXTURE_CADDY_INTEGRITY")
    key = private_tls_key()
    installation.write("data/tls/key.pem", key)
    installation.write(
        "data/tls/cert.pem", certificate("fixture.test", "10.231.0.1", key)
    )
    root = installation.target
    config = root / "fixture-agent.Caddyfile"
    config.write_text(
        "{\n admin off\n persist_config off\n auto_https off\n}\nhttps://fixture.test {\n"
        " bind 10.231.0.1\n tls "
        + json.dumps(str(root / "data/tls/cert.pem"))
        + " "
        + json.dumps(str(root / "data/tls/key.pem"))
        + "\n"
        + agent_handle("https://127.0.0.1:" + str(core.port), core.root / "tls.pem")
        + " handle {\n respond 404\n }\n}\n",
        encoding="utf-8",
    )
    with (root / "fixture-agent.log").open("wb") as log:
        process = subprocess.Popen(
            [str(args.caddy), "run", "--config", str(config), "--adapter", "caddyfile"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            cwd=root,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(root),
                "XDG_DATA_HOME": str(root / "caddy-data"),
                "XDG_CONFIG_HOME": str(root / "caddy-config"),
            },
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise ValueError("E_FIXTURE_CADDY_START")
                try:
                    with socket.create_connection(("10.231.0.1", 443), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise ValueError("E_FIXTURE_CADDY_READINESS")
            yield
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def exercise(args):
    if not sys.platform.startswith("linux") or os.geteuid() == 0:
        raise ValueError("E_FIXTURE_UNPRIVILEGED_LINUX_REQUIRED")
    runpy.run_path(str(Path(__file__).with_name("verify-linux-core.py")))[
        "isolated_namespace"
    ]()
    for path, digest in (
        (args.installer, args.installer_sha256),
        (args.core_jar, args.core_sha256),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("E_FIXTURE_INPUT_INTEGRITY")
    version = subprocess.check_output(
        [str(args.installer), "--version"], text=True, timeout=30
    ).strip()
    if version != args.installer_version:
        raise ValueError("E_FIXTURE_INSTALLER_VERSION")
    helpers = runpy.run_path(
        str(Path(__file__).with_name("verify-application-restore.py"))
    )
    invoke = runpy.run_path(str(Path(__file__).with_name("verify-installer-node.py")))[
        "invoke"
    ]
    root = args.work / ("pairing-transfer-" + secrets.token_hex(8))
    root.mkdir(mode=0o700)
    installation = helpers["fixture_installation"](root / "core")
    helpers["keys"](installation)
    with (
        PostgresFixture(args.postgres_bin) as postgres,
        contextlib.ExitStack() as stack,
    ):
        postgres.query("postgres", "CREATE DATABASE pairing_transfer_fixture")
        core = helpers["CoreProcess"](
            installation, postgres, "pairing_transfer_fixture", args.java, args.core_jar
        )
        stack.callback(core.stop_application)
        core.activate()
        owner = core.request(
            "POST",
            "/v1/auth/setup",
            {
                "username": "pairing-transfer-fixture",
                "password": secrets.token_urlsafe(32),
                "spaceType": "BUSINESS",
                "spaceName": "Pairing transfer fixture",
            },
            bootstrap=(installation.target / "secrets/bootstrap.secret")
            .read_text()
            .strip(),
        )

        class AuthenticatedOwner:
            def __init__(self):
                self.installation = installation

            def request(self, method, route, body=None):
                return core.request(method, route, body, token=owner["sessionToken"])

        client = AuthenticatedOwner()
        if client.request("GET", "/v1/space")["type"] != "BUSINESS":
            raise ValueError("E_FIXTURE_BUSINESS_SPACE")
        stack.enter_context(proxy(args, installation, core))
        messages = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
        output = io.StringIO()
        with (
            patch(
                "builtins.input", side_effect=["PAIR", "Transferred node", "PAIR", "0"]
            ),
            contextlib.redirect_stdout(output),
        ):
            guided_devices(client, messages)
        paths = list(installation.target.glob("pairing-transfer-*/pairing.json"))
        if len(paths) != 1:
            raise ValueError("E_FIXTURE_PAIRING_EXPORT")
        path = paths[0]
        pairing = load(path)
        if pairing is None or pairing.core_url != "https://fixture.test":
            raise ValueError("E_FIXTURE_CONFIGURED_ORIGIN")
        config = root / "target/agent.json"
        code, captured = invoke(
            args.installer,
            [
                "--prepare-node",
                "--node-config",
                str(config),
                "--node-pairing",
                str(path),
            ],
            b"en\nPAIR\n",
            root,
        )
        if code or not config.is_file():
            (root / "target-installer.log").write_bytes(captured)
            raise ValueError("E_FIXTURE_PAIRING_NATIVE_IMPORT")
        original = config.read_bytes()
        if core.command("SELECT count(*) FROM gateway_node").strip() != b"1":
            raise ValueError("E_FIXTURE_PAIRING_NODE_COUNT")
        if (
            core.command("SELECT owner_id FROM gateway_node").strip().decode()
            != pairing.space_id
        ):
            raise ValueError("E_FIXTURE_PAIRING_SPACE_BINDING")
        failed, replay_output = invoke(
            args.installer,
            [
                "--prepare-node",
                "--node-config",
                str(root / "replay/agent.json"),
                "--node-pairing",
                str(path),
            ],
            b"en\nPAIR\n",
            root,
        )
        if failed == 0 or (root / "replay/agent.json").exists():
            raise ValueError("E_FIXTURE_CONSUMED_TRANSFER_REUSED")
        expired_path, expiring = export(client, "Deliberately expired fixture")
        # Explicit disposable-database mutation exercises server expiry without
        # waiting ten minutes or replacing Core's validation with a fake response.
        core.command(
            "UPDATE gateway_enrollment SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE id='"
            + expiring.enrollment_id
            + "'"
        )
        failed, expiry_output = invoke(
            args.installer,
            [
                "--prepare-node",
                "--node-config",
                str(root / "expired/agent.json"),
                "--node-pairing",
                str(expired_path),
            ],
            b"en\nPAIR\n",
            root,
        )
        if failed == 0 or (root / "expired/agent.json").exists():
            raise ValueError("E_FIXTURE_EXPIRED_TRANSFER_ACCEPTED")
        if (
            config.read_bytes() != original
            or core.command("SELECT count(*) FROM gateway_node").strip() != b"1"
        ):
            raise ValueError("E_FIXTURE_TRANSFER_IDENTITY_CHANGED")
        for secret in (
            pairing.token,
            expiring.token,
            json.loads(original)["gateway_token"],
            owner["sessionToken"],
        ):
            if (
                secret.encode()
                in captured + replay_output + expiry_output + output.getvalue().encode()
            ):
                raise ValueError("E_FIXTURE_SECRET_OUTPUT")
        node = core.request(
            "GET", "/v1/gateways/management", token=owner["sessionToken"]
        )[0]
        if node["allowedTasks"] != []:
            raise ValueError("E_FIXTURE_TRANSFER_IMPLICIT_TASKS")
        return {
            "installerVersion": version,
            "installerSha256": args.installer_sha256,
            "coreJarSha256": args.core_sha256,
            "actualCorePostgreSqlAndPinnedTls": True,
            "actualConfiguredOriginAndCaddyIngress": True,
            "actualOwnerEnrollmentExport": True,
            "actualFrozenTargetTransferImport": True,
            "serverRejectsConsumedCode": True,
            "serverRejectsExpiredCode": True,
            "serverExpiryControlledInDisposableDatabase": True,
            "existingIdentityPreserved": True,
            "noImplicitTaskGrants": True,
            "businessSpacePreserved": True,
            "secretsAbsentFromCapturedOutput": True,
            "terminalChoicesInjected": True,
            "ownerTransportUsesProcessFixtureAdapter": True,
            "coreOrAgentSuccessResponsesMocked": False,
            "actualProviderBrowserLogin": False,
            "actualOperatingSystemService": False,
            "networkNamespaceIsolated": True,
            "realHouseholdActions": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "installer",
        "core-jar",
        "java",
        "postgres-bin",
        "caddy",
        "work",
        "report",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in (
        "installer-sha256",
        "installer-version",
        "core-sha256",
        "caddy-sha256",
    ):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = exercise(args)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
