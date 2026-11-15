"""Actual systemd/UID/frozen-worker/Core fixture; no provider or household action."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import pwd
import runpy
import secrets
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from postgres_fixture import PostgresFixture


def wait_json(path: Path, *, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                return json.loads(path.read_bytes())
            except json.JSONDecodeError:
                pass
        time.sleep(0.2)
    raise ValueError("E_FIXTURE_RESPONSE_TIMEOUT")


def child(args):
    def terminate(*_):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    helpers = runpy.run_path(
        str(Path(__file__).with_name("verify-application-restore.py"))
    )
    installation = helpers["fixture_installation"](args.work / "core")
    helpers["keys"](installation)
    with (
        PostgresFixture(args.postgres_bin) as postgres,
        contextlib.ExitStack() as stack,
    ):
        postgres.query("postgres", "CREATE DATABASE node_service_fixture")
        core = helpers["CoreProcess"](
            installation, postgres, "node_service_fixture", args.java, args.core_jar
        )
        stack.callback(core.stop_application)
        core.activate()
        owner = core.request(
            "POST",
            "/v1/auth/setup",
            {
                "username": "node-service-fixture",
                "password": secrets.token_urlsafe(32),
                "spaceType": "HOME",
                "spaceName": "Node service fixture",
            },
            bootstrap=(installation.target / "secrets/bootstrap.secret")
            .read_text()
            .strip(),
        )
        enrollment = core.request(
            "POST",
            "/v1/gateways/enrollments",
            {
                "displayName": "Systemd prepared node fixture",
            },
            token=owner["sessionToken"],
        )
        code = args.work / "pairing-code"
        code.write_text(enrollment["enrollmentToken"], encoding="ascii")
        code.chmod(0o600)
        from node_pairing import validate

        pairing = validate(
            {
                "formatVersion": 1,
                "kind": "kyrion-device-pairing",
                "coreUrl": "https://127.0.0.1:" + str(core.port),
                "certificate": (core.root / "tls.pem").read_text(encoding="ascii"),
                "certificateSha256": hashlib.sha256(
                    (core.root / "tls.pem").read_bytes()
                ).hexdigest(),
                "enrollmentId": enrollment["id"],
                "expiresAt": enrollment["expiresAt"],
                "enrollmentToken": enrollment["enrollmentToken"],
                "spaceId": core.request(
                    "GET", "/v1/space", token=owner["sessionToken"]
                )["id"],
                "installationId": installation.state["installationId"],
            }
        )
        transfer = args.work / "pairing.json"
        transfer.write_text(json.dumps(pairing.document()), encoding="utf-8")
        transfer.chmod(0o600)
        (args.work / "ready.json").write_text(
            json.dumps(
                {
                    "url": "https://127.0.0.1:" + str(core.port),
                    "certificate": str(core.root / "tls.pem"),
                    "token": str(code),
                    "pairing": str(transfer),
                }
            ),
            encoding="utf-8",
        )
        deadline = time.monotonic() + 600
        seen = None
        while time.monotonic() < deadline:
            request = args.work / "request.json"
            if request.exists():
                value = json.loads(request.read_bytes())
                if value["id"] != seen:
                    seen = value["id"]
                    if value["action"] == "exit":
                        return
                    if value["action"] == "stop":
                        core.stop_application()
                    elif value["action"] == "start":
                        core.activate()
                    elif value["action"] == "revoke":
                        node = core.request(
                            "GET",
                            "/v1/gateways/management",
                            token=owner["sessionToken"],
                        )[0]
                        core.request(
                            "DELETE",
                            "/v1/gateways/" + node["id"],
                            {"revision": node["revision"]},
                            token=owner["sessionToken"],
                        )
                    elif value["action"] != "count":
                        raise ValueError("E_FIXTURE_ACTION")
                    result = {
                        "id": seen,
                        "nodes": int(
                            core.command("SELECT count(*) FROM gateway_node").strip()
                        ),
                    }
                    (args.work / (seen + ".json")).write_text(
                        json.dumps(result), encoding="utf-8"
                    )
            time.sleep(0.1)
        raise ValueError("E_FIXTURE_TIMEOUT")


def exercise(args):
    from host import reject_links
    from node_service import load, service_state
    from update_schedule import systemctl

    if os.geteuid() != 0 or not Path("/run/systemd/system").is_dir():
        raise ValueError("E_FIXTURE_SYSTEMD_ROOT_REQUIRED")
    reject_links(args.work)
    if args.work.stat().st_uid != 0 or args.work.stat().st_mode & 0o022:
        raise ValueError("E_FIXTURE_ROOT")
    for path, digest in (
        (args.installer, args.installer_sha256),
        (args.core_jar, args.core_sha256),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("E_FIXTURE_INPUT_INTEGRITY")
    fixture_user = pwd.getpwnam(args.fixture_user)
    if fixture_user.pw_uid == 0:
        raise ValueError("E_FIXTURE_USER")
    root = args.work / ("node-service-" + uuid.uuid4().hex)
    root.mkdir(mode=0o755)
    (root / "fixture.json").write_text(
        json.dumps({"scope": "installer-node-service-development-fixture"}),
        encoding="utf-8",
    )
    data = root / "core-fixture"
    data.mkdir(mode=0o700)
    os.chown(data, fixture_user.pw_uid, fixture_user.pw_gid)
    target = root / "installed"

    def send_request(value):
        temporary = data / (".request-" + uuid.uuid4().hex)
        with os.fdopen(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as stream:
            stream.write(json.dumps(value).encode())
            stream.flush()
            os.fsync(stream.fileno())
            os.fchown(stream.fileno(), fixture_user.pw_uid, fixture_user.pw_gid)
        os.replace(temporary, data / "request.json")

    child_arguments = [
        "/usr/sbin/runuser",
        "-u",
        args.fixture_user,
        "--",
        sys.executable,
        str(Path(__file__).resolve()),
        "--core-child",
        "--work",
        str(data),
        "--postgres-bin",
        str(args.postgres_bin),
        "--java",
        str(args.java),
        "--core-jar",
        str(args.core_jar),
    ]
    with (root / "core-fixture.log").open("wb") as log:
        process = subprocess.Popen(
            child_arguments,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
        try:
            ready = wait_json(data / "ready.json")
            invoke = runpy.run_path(
                str(Path(__file__).with_name("verify-installer-node.py"))
            )["invoke"]
            arguments = [
                "--node-service",
                "install",
                "--target",
                str(target),
                "--node-pairing",
                ready["pairing"],
            ]
            code, output = invoke(args.installer, arguments, b"en\nSERVICE\n", root)
            (root / "installer.log").write_bytes(output)
            if code:
                raise ValueError("E_FIXTURE_NODE_SERVICE_INSTALL")
            installation = load(target)
            if (
                installation.configuration["manifestSha256"]
                != hashlib.sha256(
                    (target / installation.state["nodeWorker"]).read_bytes()
                ).hexdigest()
            ):
                raise ValueError("E_FIXTURE_NODE_WORKER_INTENT")
            unit = service_state(installation)["unit"]
            account = pwd.getpwnam(installation.state["nodeAccount"]["name"])
            if account.pw_uid == 0 or account.pw_shell != "/usr/sbin/nologin":
                raise ValueError("E_FIXTURE_SERVICE_UID")

            def wait_state(expected, timeout=80):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    actual = service_state(load(target))
                    if (
                        actual["active"]
                        and actual["enabled"]
                        and actual["coreConnection"] == expected
                    ):
                        return actual
                    time.sleep(0.5)
                raise ValueError("E_FIXTURE_NODE_SERVICE_" + expected.upper())

            def command(action):
                identifier = uuid.uuid4().hex
                send_request({"id": identifier, "action": action})
                return wait_json(data / (identifier + ".json"))

            wait_state("connected")
            credentials = (target / "agent/agent.json").read_bytes()
            same_inputs, _ = invoke(args.installer, arguments, b"en\nSERVICE\n", root)
            if same_inputs or (target / "agent/agent.json").read_bytes() != credentials:
                raise ValueError("E_FIXTURE_NODE_SERVICE_REPEAT_INPUTS")
            foreign_code = root / "different-pairing.json"
            conflicting_value = json.loads(Path(ready["pairing"]).read_bytes())
            conflicting_value["enrollmentToken"] = secrets.token_urlsafe(32)
            foreign_code.write_text(json.dumps(conflicting_value), encoding="utf-8")
            foreign_code.chmod(0o600)
            conflicting = list(arguments)
            conflicting[conflicting.index("--node-pairing") + 1] = str(foreign_code)
            rejected, _ = invoke(args.installer, conflicting, b"en\nSERVICE\n", root)
            if (
                rejected == 0
                or (target / "agent/agent.json").read_bytes() != credentials
            ):
                raise ValueError("E_FIXTURE_NODE_SERVICE_RETARGET")
            systemctl("restart", unit)
            wait_state("connected")
            repeated, _ = invoke(
                args.installer,
                ["--node-service", "install", "--target", str(target)],
                b"en\nSERVICE\n",
                root,
            )
            if (
                repeated
                or (target / "agent/agent.json").read_bytes() != credentials
                or command("count")["nodes"] != 1
            ):
                raise ValueError("E_FIXTURE_NODE_SERVICE_IDENTITY")
            command("stop")
            wait_state("disconnected")
            command("start")
            wait_state("connected")
            disabled, _ = invoke(
                args.installer,
                ["--node-service", "disable", "--target", str(target)],
                b"en\nSERVICE\n",
                root,
            )
            state = service_state(load(target))
            if disabled or state["active"] or state["enabled"]:
                raise ValueError("E_FIXTURE_NODE_SERVICE_DISABLE")
            repaired, _ = invoke(
                args.installer,
                ["--node-service", "repair", "--target", str(target)],
                b"en\nSERVICE\n",
                root,
            )
            if repaired:
                raise ValueError("E_FIXTURE_NODE_SERVICE_REPAIR")
            wait_state("connected")
            removed, _ = invoke(
                args.installer,
                ["--node-service", "remove", "--target", str(target)],
                b"en\nSERVICE\n",
                root,
            )
            if (
                removed
                or service_state(load(target))["registered"]
                or (target / "agent/agent.json").read_bytes() != credentials
            ):
                raise ValueError("E_FIXTURE_NODE_SERVICE_REMOVE")
            command("count")
            credential = json.loads(credentials)["gateway_token"].encode()
            if credential in output:
                raise ValueError("E_FIXTURE_SECRET_OUTPUT")
            return {
                "actualSystemdSystemService": True,
                "actualNonRootDedicatedUid": True,
                "actualFrozenInstallerAndWorker": True,
                "actualPairingTransferServiceSetup": True,
                "pairingFileBuiltFromActualCoreEnrollment": True,
                "installerSha256": args.installer_sha256,
                "coreJarSha256": args.core_sha256,
                "actualCorePostgreSQLTls": True,
                "actualConfirmedCoreHeartbeat": True,
                "actualServiceRestart": True,
                "sameIdentityAfterRepeat": True,
                "sameReviewedInputsAreIdempotent": True,
                "conflictingEnrollmentInputRejected": True,
                "actualCoreLossAndReconnect": True,
                "actualDisableRepairAndServiceRemoval": True,
                "credentialsPreserved": True,
                "coreOrAgentResponsesMocked": False,
                "actualKernelColdBoot": False,
                "isolatedDevelopmentDistro": True,
                "separateNetworkNamespace": False,
                "realHouseholdActions": False,
                "fixtureRoot": str(root),
            }
        finally:
            if target.exists():
                try:
                    from node_service import owned_unit

                    installation = load(target)
                    unit_path = owned_unit(installation)
                    if unit_path.exists():
                        systemctl("disable", "--now", unit_path.name)
                        unit_path.unlink()
                        systemctl("daemon-reload")
                except (OSError, ValueError, KeyError):
                    pass  # Preserve the exact fixture for diagnosis; never remove foreign resources.
            if process.poll() is None:
                send_request({"id": uuid.uuid4().hex, "action": "exit"})
            try:
                process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-child", action="store_true")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--installer-sha256")
    parser.add_argument("--core-jar", type=Path, required=True)
    parser.add_argument("--core-sha256")
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--fixture-user", default="kyrion-fixture")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.core_child:
        child(args)
    else:
        result = exercise(args)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
