"""Actual frozen Linux installer/Core/PostgreSQL/TLS with supplied terminal choices."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import runpy
import secrets
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from postgres_fixture import PostgresFixture

helpers = runpy.run_path(
    str(Path(__file__).with_name("verify-application-restore.py")),
    run_name="node_core_helpers",
)


@contextlib.contextmanager
def agent_proxy(core, caddy, expected_digest, root):
    from node_transport import agent_handle

    if hashlib.sha256(caddy.read_bytes()).hexdigest() != expected_digest:
        raise ValueError("E_FIXTURE_CADDY_INTEGRITY")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = root / "agent.Caddyfile"
    config.write_text(
        "{\n admin off\n persist_config off\n auto_https off\n}\nhttps://127.0.0.1:"
        + str(port)
        + " {\n bind 127.0.0.1\n tls "
        + json.dumps(str(core.root / "tls.pem"))
        + " "
        + json.dumps(str(core.root / "tls.key"))
        + "\n"
        + agent_handle("https://127.0.0.1:" + str(core.port), core.root / "tls.pem")
        + " handle {\n respond 404\n }\n}\n",
        encoding="utf-8",
    )
    with (root / "agent-proxy.log").open("wb") as log:
        child = subprocess.Popen(
            [str(caddy), "run", "--config", str(config), "--adapter", "caddyfile"],
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
                if child.poll() is not None:
                    raise ValueError("E_FIXTURE_CADDY_START")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise ValueError("E_FIXTURE_CADDY_READINESS")
            yield "https://127.0.0.1:" + str(port)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)


@contextlib.contextmanager
def running(
    installer,
    arguments,
    answers,
    work,
    *,
    provider_directory=None,
    provider_record=None,
):
    import pty

    master, slave = pty.openpty()
    child = None
    try:
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(work), "LANG": "C.UTF-8"}
        if provider_directory is not None:
            environment["PATH"] = str(provider_directory) + ":/usr/bin:/bin"
            environment["KYRION_FIXTURE_COMMAND_FILE"] = str(provider_record)
        child = subprocess.Popen(
            [str(installer), *arguments],
            stdin=slave,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
        )
        os.close(slave)
        slave = None
        os.write(master, answers)
        yield child
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        os.close(master)
        if slave is not None:
            os.close(slave)


def invoke(installer, arguments, answers, work):
    with running(installer, arguments, answers, work) as child:
        try:
            output, error = child.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            raise ValueError("E_FIXTURE_INSTALLER_TIMEOUT") from None
        return child.returncode, output + error


def exercise(args):
    if (
        not sys.platform.startswith("linux")
        or helpers["packaged_schema"](args.core_jar) != 51
    ):
        raise ValueError("E_FIXTURE_PLATFORM")
    for path, expected in (
        (args.installer, args.installer_sha256),
        (args.core_jar, args.core_sha256),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("E_FIXTURE_INPUT_INTEGRITY")
    runpy.run_path(str(Path(__file__).with_name("verify-linux-core.py")))[
        "isolated_namespace"
    ]()
    version = subprocess.check_output(
        [str(args.installer), "--version"], timeout=30, text=True
    ).strip()
    if version != args.installer_version:
        raise ValueError("E_FIXTURE_INSTALLER_VERSION")
    root = args.work / ("frozen-node-" + secrets.token_hex(8))
    root.mkdir(mode=0o700)
    installation = helpers["fixture_installation"](root / "core")
    helpers["keys"](installation)
    with (
        PostgresFixture(args.postgres_bin) as postgres,
        contextlib.ExitStack() as stack,
    ):
        postgres.query("postgres", "CREATE DATABASE frozen_node_fixture")
        core = helpers["CoreProcess"](
            installation, postgres, "frozen_node_fixture", args.java, args.core_jar
        )
        stack.callback(core.stop_application)
        core.activate()
        origin = "https://127.0.0.1:" + str(core.port)
        if args.caddy is not None:
            origin = stack.enter_context(
                agent_proxy(core, args.caddy, args.caddy_sha256, root)
            )
        owner = core.request(
            "POST",
            "/v1/auth/setup",
            {
                "username": "frozen-node-fixture",
                "password": secrets.token_urlsafe(32),
                "spaceType": "HOME",
                "spaceName": "Frozen node fixture",
            },
            bootstrap=(installation.target / "secrets/bootstrap.secret")
            .read_text()
            .strip(),
        )
        enrollment = core.request(
            "POST",
            "/v1/gateways/enrollments",
            {"displayName": "Frozen installer node"},
            token=owner["sessionToken"],
        )
        token_file = root / "pairing-code"
        token_file.write_text(enrollment["enrollmentToken"], encoding="ascii")
        token_file.chmod(0o600)
        config = root / "agent/agent.json"
        arguments = [
            "--prepare-node",
            "--node-config",
            str(config),
            "--node-url",
            origin,
            "--node-token-file",
            str(token_file),
            "--node-certificate",
            str(core.root / "tls.pem"),
        ]
        code, output = invoke(args.installer, arguments, b"en\nPAIR\n", args.work)
        if code or not config.is_file():
            raise ValueError("E_FIXTURE_FROZEN_NODE_ENROLLMENT")
        original = config.read_bytes()
        private = json.loads(original)
        if (
            config.stat().st_mode & 0o777 != 0o600
            or config.stat().st_uid != os.geteuid()
        ):
            raise ValueError("E_FIXTURE_NODE_STORAGE")
        repeated, second = invoke(args.installer, arguments, b"en\nPAIR\n", args.work)
        if (
            repeated == 0
            or config.read_bytes() != original
            or core.command("SELECT count(*) FROM gateway_node").strip() != b"1"
        ):
            raise ValueError("E_FIXTURE_NODE_IDENTITY_OVERWRITE")
        heartbeat = ["--node-heartbeat", "--node-config", str(config)]
        status, health = invoke(
            args.installer, heartbeat, b"en\nHEARTBEAT\n", args.work
        )
        if status or b'"heartbeatAcknowledged": true' not in health:
            raise ValueError("E_FIXTURE_FROZEN_HEARTBEAT")
        observed = core.request(
            "GET", "/v1/gateways/management", token=owner["sessionToken"]
        )[0]
        if (
            observed["id"] != private["node_id"]
            or observed["availability"] not in {"online", "degraded"}
            or observed["allowedTasks"] != []
            or observed["agentVersion"] != "0.2.0"
        ):
            raise ValueError("E_FIXTURE_FROZEN_NODE_OBSERVATION")
        core.stop_application()
        core.activate()
        restarted, after = invoke(
            args.installer, heartbeat, b"en\nHEARTBEAT\n", args.work
        )
        if restarted or config.read_bytes() != original:
            raise ValueError("E_FIXTURE_FROZEN_NODE_RESTART")
        foreground = ["--node-run", "--node-config", str(config)]
        providers = root / "synthetic-provider"
        providers.mkdir(mode=0o700)
        record = root / "synthetic-command.jsonl"
        # This provider only records the single synthetic operation. It never
        # contacts MQTT or a physical controller. Core and agent transport stay real.
        publisher = providers / "mosquitto_pub"
        publisher.write_text(
            """#!/usr/bin/python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
assert args[args.index('-h')+1]=='127.0.0.1'
assert args[args.index('-t')+1]=='zigbee2mqtt/bridge/request/permit_join'
body=json.loads(args[args.index('-m')+1]);assert body=={'value':False,'time':0}
path=Path(os.environ['KYRION_FIXTURE_COMMAND_FILE'])
assert path.is_absolute() and path.resolve().is_relative_to(Path(os.environ['HOME']).resolve())
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as stream:stream.write(json.dumps(body)+'\\n')
""",
            encoding="utf-8",
        )
        publisher.chmod(0o700)
        subscriber = providers / "mosquitto_sub"
        subscriber.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        subscriber.chmod(0o700)
        last_seen = core.command("SELECT last_seen_at::text FROM gateway_node").strip()
        daemon = stack.enter_context(
            running(
                args.installer,
                foreground,
                b"en\nRUN\n",
                args.work,
                provider_directory=providers,
                provider_record=record,
            )
        )

        def wait_report(previous):
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if daemon.poll() is not None:
                    raise ValueError("E_FIXTURE_NODE_RUNTIME_EXIT")
                current = core.command(
                    "SELECT last_seen_at::text FROM gateway_node"
                ).strip()
                if current != previous:
                    return current
                time.sleep(0.5)
            raise ValueError("E_FIXTURE_NODE_RUNTIME_REPORT")

        connected = wait_report(last_seen)
        try:
            core.request(
                "POST",
                "/v1/gateways/" + observed["id"] + "/zigbee/pairing",
                {"duration": 0},
                token=owner["sessionToken"],
            )
        except HTTPError as denied_without_task:
            if denied_without_task.code != 400:
                raise
        else:
            raise ValueError("E_FIXTURE_UNASSIGNED_COMMAND_ACCEPTED")
        core.request(
            "PUT",
            "/v1/gateways/" + observed["id"] + "/tasks",
            {"revision": observed["revision"], "allowedTasks": ["integration"]},
            token=owner["sessionToken"],
        )
        command = core.request(
            "POST",
            "/v1/gateways/" + observed["id"] + "/zigbee/pairing",
            {"duration": 0},
            token=owner["sessionToken"],
        )
        command_id = str(uuid.UUID(command["id"]))
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            outcome = core.command(
                "SELECT status FROM gateway_command WHERE id='" + command_id + "'"
            ).strip()
            if outcome == b"succeeded":
                break
            if outcome == b"failed" or daemon.poll() is not None:
                raise ValueError("E_FIXTURE_SYNTHETIC_COMMAND_FAILED")
            time.sleep(0.5)
        else:
            raise ValueError("E_FIXTURE_SYNTHETIC_COMMAND_TIMEOUT")
        if not record.is_file() or len(record.read_text().splitlines()) != 1:
            raise ValueError("E_FIXTURE_SYNTHETIC_COMMAND_DUPLICATED")
        duplicate, duplicate_output = invoke(
            args.installer, foreground, b"en\nRUN\n", args.work
        )
        if duplicate == 0 or b"E_AGENT_RUNTIME_BUSY" not in duplicate_output:
            raise ValueError("E_FIXTURE_DUPLICATE_NODE_RUNTIME")
        connected = core.command("SELECT last_seen_at::text FROM gateway_node").strip()
        core.stop_application()
        time.sleep(12)
        core.activate()
        wait_report(connected)
        if len(record.read_text().splitlines()) != 1:
            raise ValueError("E_FIXTURE_COMPLETED_COMMAND_REPLAYED")
        observed = core.request(
            "GET", "/v1/gateways/management", token=owner["sessionToken"]
        )[0]
        core.request(
            "DELETE",
            "/v1/gateways/" + observed["id"],
            {"revision": observed["revision"]},
            token=owner["sessionToken"],
        )
        daemon_output, daemon_error = daemon.communicate(timeout=45)
        if daemon.returncode == 0 or b"E_AGENT_ACCESS_REVOKED" not in daemon_error:
            raise ValueError("E_FIXTURE_REVOKED_RUNTIME_CONTINUES")
        if b"local task authority cleared" not in daemon_error:
            raise ValueError("E_FIXTURE_NODE_RECONNECT_NOT_OBSERVED")
        denied, last = invoke(args.installer, heartbeat, b"en\nHEARTBEAT\n", args.work)
        if denied == 0 or b'"heartbeatAcknowledged": true' in last:
            raise ValueError("E_FIXTURE_FROZEN_REVOKED_NODE")
        all_output = (
            output
            + second
            + health
            + after
            + last
            + duplicate_output
            + daemon_output
            + daemon_error
        )
        if (
            private["gateway_token"].encode() in all_output
            or enrollment["enrollmentToken"].encode() in all_output
        ):
            raise ValueError("E_FIXTURE_NODE_SECRET_OUTPUT")
        return {
            "sourceSchema": 51,
            "installerVersion": version,
            "actualFrozenInstallerProcess": True,
            "actualCorePostgreSQLAndTls": True,
            "actualAgentReverseProxy": args.caddy is not None,
            "coreJarSha256": args.core_sha256,
            "installerSha256": args.installer_sha256,
            "actualProtectedPreparedEnrollment": True,
            "repeatedEnrollmentPreservesIdentity": True,
            "actualTargetHealthReport": True,
            "actualForegroundTaskScopedRuntime": True,
            "actualLocalRuntimeMutex": True,
            "actualReconnectAfterCoreProcessLoss": True,
            "revokedForegroundRuntimeStops": True,
            "unassignedDeviceCannotEnqueueControl": True,
            "actualAuthorizedCommandTransport": True,
            "integrationCommandProviderInjected": True,
            "completedCommandNotReplayedAfterReconnect": True,
            "actualPhysicalDeviceControl": False,
            "actualCoreRestartSameNodeCredentials": True,
            "revokedNodeCannotReportSuccess": True,
            "credentialsAbsentFromOutput": True,
            "terminalChoicesSuppliedThroughPty": True,
            "separatePythonRuntimeRequiredForInstaller": False,
            "actualAgentOperatingSystemService": False,
            "actualProviderBrowserLogin": False,
            "networkNamespaceIsolated": True,
            "realHouseholdActions": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("installer", "postgres-bin", "java", "core-jar", "work", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("installer-sha256", "installer-version", "core-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--caddy", type=Path)
    parser.add_argument("--caddy-sha256")
    args = parser.parse_args()
    if (args.caddy is None) != (args.caddy_sha256 is None):
        parser.error("E_FIXTURE_CADDY_INPUT")
    result = exercise(args)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
