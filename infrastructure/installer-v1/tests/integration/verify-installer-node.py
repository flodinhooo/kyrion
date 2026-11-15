"""Actual frozen Linux installer/Core/PostgreSQL/TLS with supplied terminal choices."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import runpy
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from postgres_fixture import PostgresFixture

helpers = runpy.run_path(
    str(Path(__file__).with_name("verify-application-restore.py")),
    run_name="node_core_helpers",
)


def invoke(installer, arguments, answers, work):
    import pty

    master, slave = pty.openpty()
    try:
        child = subprocess.Popen(
            [str(installer), *arguments],
            stdin=slave,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin", "HOME": str(work), "LANG": "C.UTF-8"},
        )
        os.close(slave)
        slave = None
        os.write(master, answers)
        try:
            output, error = child.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate(timeout=10)
            raise ValueError("E_FIXTURE_INSTALLER_TIMEOUT") from None
        return child.returncode, output + error
    finally:
        os.close(master)
        if slave is not None:
            os.close(slave)


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
            "https://127.0.0.1:" + str(core.port),
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
        ):
            raise ValueError("E_FIXTURE_FROZEN_NODE_OBSERVATION")
        core.stop_application()
        core.activate()
        restarted, after = invoke(
            args.installer, heartbeat, b"en\nHEARTBEAT\n", args.work
        )
        if restarted or config.read_bytes() != original:
            raise ValueError("E_FIXTURE_FROZEN_NODE_RESTART")
        core.request(
            "DELETE",
            "/v1/gateways/" + observed["id"],
            {"revision": observed["revision"]},
            token=owner["sessionToken"],
        )
        denied, last = invoke(args.installer, heartbeat, b"en\nHEARTBEAT\n", args.work)
        if denied == 0 or b'"heartbeatAcknowledged": true' in last:
            raise ValueError("E_FIXTURE_FROZEN_REVOKED_NODE")
        all_output = output + second + health + after + last
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
            "actualProtectedPreparedEnrollment": True,
            "repeatedEnrollmentPreservesIdentity": True,
            "actualTargetHealthReport": True,
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
    args = parser.parse_args()
    result = exercise(args)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
