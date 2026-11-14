"""Actual Core/PG/TLS and separate agent processes with one lost ACK injection.

No services, existing accounts, household actions or public network are used.
The caller supplies the existing unprivileged isolated Linux fixture environment.
"""

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
    run_name="agent_core_helpers",
)
CoreProcess = helpers["CoreProcess"]


def exercise(
    postgres_bin: Path, java: Path, jar: Path, digest: str, source: Path, work: Path
) -> dict:
    if (
        os.name != "posix"
        or helpers["packaged_schema"](jar) != 50
        or hashlib.sha256(jar.read_bytes()).hexdigest() != digest
    ):
        raise ValueError("E_FIXTURE_CORE_REQUIRED")
    runpy.run_path(str(Path(__file__).with_name("verify-linux-core.py")))[
        "isolated_namespace"
    ]()
    if not (source / "kyrion_gateway_agent/enrollment.py").is_file():
        raise ValueError("E_FIXTURE_GATEWAY_SOURCE_REQUIRED")
    root = work / ("agent-enrollment-" + secrets.token_hex(8))
    root.mkdir(mode=0o700)
    installation = helpers["fixture_installation"](root / "core")
    helpers["keys"](installation)
    with PostgresFixture(postgres_bin) as postgres, contextlib.ExitStack() as stack:
        postgres.query("postgres", "CREATE DATABASE agent_fixture")
        core = CoreProcess(installation, postgres, "agent_fixture", java, jar)
        stack.callback(core.stop_application)
        core.activate()
        owner = core.request(
            "POST",
            "/v1/auth/setup",
            {
                "username": "agent-fixture-owner",
                "password": secrets.token_urlsafe(32),
                "spaceType": "BUSINESS",
                "spaceName": "Agent fixture",
            },
            bootstrap=(installation.target / "secrets/bootstrap.secret")
            .read_text()
            .strip(),
        )
        enrollment = core.request(
            "POST",
            "/v1/gateways/enrollments",
            {"displayName": "Prepared fixture"},
            token=owner["sessionToken"],
        )
        token = root / "pairing-code"
        token.write_text(enrollment["enrollmentToken"], encoding="ascii")
        token.chmod(0o600)
        config = root / "agent" / "agent.json"
        pending = config.with_name("agent.json.enrollment.json")
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "HOME": str(work),
            "PYTHONPATH": str(source),
        }
        arguments = [
            "--config",
            str(config),
            "enroll-prepared",
            "--core-url",
            "https://127.0.0.1:" + str(core.port),
            "--token-file",
            str(token),
            "--ca-certificate",
            str(core.root / "tls.pem"),
        ]
        lost = """import json,sys
from kyrion_gateway_agent import client,cli
actual=client._request
def lost_ack(url,method,*arguments,**options):
 result=actual(url,method,*arguments,**options)
 if method=='POST' and url.endswith('/enroll'):raise client.CoreRequestError('E_SYNTHETIC_ACK_LOST_AFTER_COMMIT')
 return result
client._request=lost_ack
try:cli.main()
except client.CoreRequestError as error:
 if str(error)!='E_SYNTHETIC_ACK_LOST_AFTER_COMMIT':raise
 print(json.dumps({'deliberateAckLoss':True}));sys.exit(75)
"""
        first = subprocess.run(
            [sys.executable, "-c", lost, *arguments],
            env=environment,
            capture_output=True,
            check=False,
            timeout=60,
        )
        if first.returncode != 75 or not pending.is_file() or config.exists():
            raise ValueError("E_FIXTURE_ACK_INTERRUPTION")
        private = json.loads(pending.read_bytes())
        if (
            pending.stat().st_mode & 0o777 != 0o600
            or pending.stat().st_uid != os.geteuid()
        ):
            raise ValueError("E_FIXTURE_PENDING_PROTECTION")
        before = core.command("SELECT id::text FROM gateway_node").strip().decode()
        if (
            not before
            or core.command("SELECT count(*) FROM gateway_node").strip() != b"1"
        ):
            raise ValueError("E_FIXTURE_COMMITTED_NODE_MISSING")
        second = subprocess.run(
            [
                sys.executable,
                "-c",
                "from kyrion_gateway_agent.cli import main;main()",
                "--config",
                str(config),
                "enroll-prepared",
            ],
            env=environment,
            capture_output=True,
            check=False,
            timeout=60,
        )
        if (
            second.returncode
            or pending.exists()
            or config.stat().st_mode & 0o777 != 0o600
        ):
            raise ValueError("E_FIXTURE_AGENT_RESUME")
        if (
            json.loads(second.stdout)["nodeId"] != before
            or core.command("SELECT count(*) FROM gateway_node").strip() != b"1"
        ):
            raise ValueError("E_FIXTURE_DUPLICATE_NODE")
        if (
            core.command(
                "SELECT count(*) FROM activity_event WHERE event_type='gateway.registered'"
            ).strip()
            != b"1"
        ):
            raise ValueError("E_FIXTURE_DUPLICATE_ENROLLMENT_AUDIT")
        if (
            private["node_credential"].encode()
            in first.stdout + first.stderr + second.stdout + second.stderr
        ):
            raise ValueError("E_FIXTURE_CREDENTIAL_OUTPUT")
        authenticated = """import json,sys
from pathlib import Path
from kyrion_gateway_agent.client import next_command
from kyrion_gateway_agent.config import AgentConfig
config=AgentConfig.load(Path(sys.argv[1]))
assert config.local_only
assert next_command(config) is None
print(json.dumps({'authenticated':True}))
"""
        third = subprocess.run(
            [sys.executable, "-c", authenticated, str(config)],
            env=environment,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if (
            third.returncode
            or json.loads(third.stdout).get("authenticated") is not True
        ):
            raise ValueError("E_FIXTURE_AGENT_AUTHENTICATION")
        ca = config.with_name("agent.json.ca.pem")
        original_ca = ca.read_bytes()
        try:
            ca.write_bytes(original_ca + b"\n")
            rejected = subprocess.run(
                [sys.executable, "-c", authenticated, str(config)],
                env=environment,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if (
                rejected.returncode == 0
                or b"E_AGENT_TLS_CONFIGURATION" not in rejected.stderr
            ):
                raise ValueError("E_FIXTURE_CHANGED_TRUST_ACCEPTED")
        finally:
            ca.write_bytes(original_ca)
        return {
            "sourceSchema": 50,
            "actualCorePostgreSQLAndAgentProcesses": True,
            "actualVerifiedLocalTls": True,
            "actualPrivatePendingBeforeRequest": True,
            "actualServerCommitBeforeDeliberateLostAck": True,
            "actualNewProcessResumeSameIdentity": True,
            "singleNodeAndSingleAuditEvent": True,
            "actualAuthenticatedEmptyPoll": True,
            "changedCaRefused": True,
            "credentialNotInChildOutput": True,
            "networkNamespaceIsolated": True,
            "ackLossFaultInjected": True,
            "actualSCMOrSystemdAgentService": False,
            "actualWindowsPreparedAgent": False,
            "realHouseholdActions": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "postgres-bin",
        "java",
        "core-jar",
        "gateway-source",
        "work",
        "report",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--core-sha256", required=True)
    args = parser.parse_args()
    result = exercise(
        args.postgres_bin.resolve(),
        args.java.resolve(),
        args.core_jar.resolve(),
        args.core_sha256,
        args.gateway_source.resolve(),
        args.work.resolve(),
    )
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
