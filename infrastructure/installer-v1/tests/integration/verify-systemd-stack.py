"""Actual single-host stack/update/startup test in the explicitly owned guest.

Only the startup unit's network namespace is fixture-specific. No eligibility,
systemd, Docker, readiness, identity, migration or recovery probes are injected.
The deliberate activation interruption is fault injection. SSO is not accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pty
import re
import runpy
import secrets
import select
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import runtime
import update_transaction
from bundle import authenticated_review
from linux_startup import disable_owned, unit_name
from onboarding import CoreClient
from recovery import load_installation
from update_compose import Compose
from update_gate import fenced
from update_schedule import systemctl


def capture_runtime_failure(installed):
    if installed.exists() and (installed / "compose.yml").is_file():
        state = load_installation(installed, verify=False).state
        commands = [
            "docker",
            "compose",
            "--project-name",
            "kyrion-" + state["installationId"],
            "--project-directory",
            str(installed),
            "--env-file",
            str(installed / ".env"),
            "-f",
            str(installed / "compose.yml"),
        ]
        if (installed / "compose-startup.yml").exists():
            commands += ["-f", str(installed / "compose-startup.yml")]
        replay_error = b""
        if not fenced(state) and state.get("authority") is None:
            replay = subprocess.run(
                [*commands, "up", "-d", "--pull", "never"],
                capture_output=True,
                check=False,
                timeout=60,
            )
            replay_error = replay.stderr
        logs = subprocess.run(
            [*commands, "logs", "--no-color", "--tail", "80"],
            capture_output=True,
            check=False,
            timeout=30,
        )
        raw = (replay_error + logs.stdout + logs.stderr).decode(errors="replace")
        # Local private developer evidence; never print arbitrary service logs.
        log = installed.parent / "private-runtime-failure.log"
        with os.fdopen(
            os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
        ) as stream:
            stream.write(raw)
        codes = sorted(
            set(
                re.findall(
                    r"\b(?:[A-Za-z]+\.)*[A-Za-z]+Exception\b|\bE_[A-Z_]{2,80}\b",
                    raw,
                )
            )
        )
        categories = [
            item
            for item in (
                "Permission denied",
                "Connection refused",
                "OutOfMemory",
                "FATAL",
                "checksum",
                "not found",
                "No space left",
                "OCI runtime",
                "mount",
                "permission",
                "network",
                "seccomp",
                "unhealthy",
                "timeout",
            )
            if item.lower() in raw.lower()
        ]
        print(
            json.dumps(
                {"failureExceptionTypes": codes, "failureCategories": categories}
            ),
            flush=True,
        )


def configure_native(worker, target):
    master, slave = pty.openpty()
    try:
        process = subprocess.Popen(
            [
                str(worker),
                "--autostart",
                "enable",
                "--target",
                str(target),
            ],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)
        slave = None
        # Explicit intent for this disposable fixture; no production bypass flag.
        os.write(master, b"en\nMAINTAIN\nCONFIGURE-STARTUP\n")
        deadline = time.monotonic() + 300
        output = bytearray()
        while time.monotonic() < deadline:
            if select.select([master], [], [], 1)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
            if process.poll() is not None:
                break
        if process.poll() is None:
            process.terminate()
        if process.wait(timeout=30):
            # Only this action's public OS summary is retained, no auth exchange.
            (target.parent / "startup-cli.txt").write_bytes(output)
            raise ValueError("E_TEST_NATIVE_STARTUP")
    finally:
        os.close(master)
        if slave is not None:
            os.close(slave)


def exercise(root, worker):
    record = json.loads((root / "fixture.json").read_bytes())
    marker = json.loads(Path("/work/kyrion-systemd-fixture.json").read_bytes())
    if (
        marker.get("scope") != "installer-systemd-development-fixture"
        or record.get("scope") != "installer-systemd-stack-fixture"
        or record.get("root") != str(root)
        or root.parent != Path("/work/systemd-stack-fixtures")
        or os.geteuid() != 0
        or Path("/proc/1/comm").read_text().strip() != "systemd"
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    if subprocess.check_output(["docker", "ps", "-aq"]).strip():
        raise ValueError("E_TEST_EMPTY_DAEMON_REQUIRED")
    with Path("/etc/hosts").open("a") as hosts:
        hosts.write("\n10.231.0.1 fixture.test\n")
    # Public source build identity for a private synthetic released-version test.
    (ROOT / "installer-build.json").write_text(
        json.dumps({"formatVersion": 1, "version": "1.0.0"})
    )
    source, target = root / "1.0.1", root / "1.0.2"
    reviewed = authenticated_review(source, source / "public.pem")
    newer = authenticated_review(target, target / "public.pem")
    installed = root / "installed"
    installation = None
    dropin = None
    network = "[Unit]\nJoinsNamespaceOf=docker.service\n[Service]\nPrivateNetwork=yes\n"
    try:
        state = runtime.provision(
            installed,
            source,
            source / "public.pem",
            "fixture.test",
            "10.231.0.1",
            reviewed.manifest_sha256,
        )
        repeated = runtime.provision(
            installed,
            source,
            source / "public.pem",
            "fixture.test",
            "10.231.0.1",
            reviewed.manifest_sha256,
        )
        if state["installationId"] != repeated["installationId"]:
            raise ValueError("E_TEST_REPEAT")
        print("actual fresh/repeated stack and TLS ready", flush=True)
        configure_native(worker, installed)
        installation = load_installation(installed)
        unit = unit_name(installation)
        directory = Path("/etc/systemd/system") / (unit + ".d")
        directory.mkdir(mode=0o700)
        dropin = directory / "fixture-network.conf"
        dropin.write_text(network)
        dropin.chmod(0o600)
        systemctl("daemon-reload")
        installation.compose("stop", "--timeout", "30")
        systemctl("start", unit)
        installation = load_installation(installed)
        if not installation.state.get("platformStartupAttempt", {}).get("healthy"):
            raise ValueError("E_TEST_REAL_SERVICE_HEALTH")
        print("actual systemd startup reached application health", flush=True)
        client = CoreClient(installation)
        credentials = {
            "username": "systemd-fixture-owner",
            "password": secrets.token_urlsafe(32),
        }
        owner = client.request(
            "POST",
            "/v1/auth/setup",
            {
                **credentials,
                "spaceType": "BUSINESS",
                "spaceName": "Synthetic systemd fixture",
            },
            bootstrap=(installed / "secrets/bootstrap.secret").read_text().strip(),
        )
        client.session = owner["sessionToken"]
        identity = client.request("GET", "/v1/auth/me")
        knowledge = installed / "data/knowledge/fixture.txt"
        knowledge.write_text("Original systemd fixture knowledge\n")
        helper = runpy.run_path(
            str(Path(__file__).with_name("verify-update-transaction.py")),
            run_name="systemd_stack_helpers",
        )
        helper["signed_inputs"](installation, target, newer)
        installation.state["updatePolicy"]["workerFile"] = installation.state[
            "startupPolicy"
        ]["workerFile"]
        installation.save()
        original = Compose(installation).identity()
        password = secrets.token_urlsafe(40)

        def interrupted(_adapter):
            raise KeyboardInterrupt("synthetic activation interruption")

        try:
            with patch.object(Compose, "activate", interrupted):
                update_transaction.apply(installed, password, review=lambda _: True)
        except KeyboardInterrupt:
            pass
        else:
            raise ValueError("E_TEST_INTERRUPTION_MISSING")
        if (
            load_installation(installed, verify=False).state["updateTransaction"][
                "phase"
            ]
            != "activating"
        ):
            raise ValueError("E_TEST_UPDATE_PHASE")
        systemctl("restart", unit)
        if (
            load_installation(installed, verify=False)
            .state["platformStartupAttempt"]
            .get("deferred")
            is not True
        ):
            raise ValueError("E_TEST_UPDATE_FENCE")
        update_transaction.resume(installed, password)
        systemctl("restart", unit)
        installation = load_installation(installed)
        if (
            not installation.state["platformStartupAttempt"]["healthy"]
            or Compose(installation).schema() != 50
        ):
            raise ValueError("E_TEST_UPDATE_HEALTH")
        print("actual update, systemd deferral and resume verified", flush=True)
        knowledge.write_text("Post-activation fixture knowledge\n")
        result = update_transaction.recover(
            installed, password, acknowledge_writes=True
        )
        installation = load_installation(installed)
        adapter = Compose(installation)
        if (
            not result["recovered"]
            or adapter.schema() != 49
            or adapter.identity() != original
            or knowledge.read_text() != "Original systemd fixture knowledge\n"
        ):
            raise ValueError("E_TEST_RECOVERY")
        client = CoreClient(installation)
        client.session = client.request("POST", "/v1/auth/login", credentials)[
            "sessionToken"
        ]
        if client.request("GET", "/v1/auth/me")["id"] != identity["id"]:
            raise ValueError("E_TEST_RECOVERY_IDENTITY")
        return {
            "actualFreshAndRepeatedStack": True,
            "actualNativeStartupRegistration": True,
            "actualSystemdApplicationStartup": True,
            "actualTlsHealth": True,
            "actualEncryptedBackupAndMigration": True,
            "actualSystemdUpdateFence": True,
            "interruptedActivationResumed": True,
            "actualRecoveryWithPreservedIdentity": True,
            "fixtureNetworkNamespaceDropin": True,
            "eligibilityOrSystemdProbesInjected": False,
            "actualBrowserSsoAccepted": False,
            "coldBootVerified": False,
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        capture_runtime_failure(installed)
        raise
    finally:
        if installed.exists():
            installation = load_installation(installed, verify=False)
            if installation.state.get("startupPolicy") is not None:
                disable_owned(installation, remove=True)
            if "compose.yml" in installation.state["files"]:
                installation.compose("down", "--timeout", "30")
        if dropin is not None:
            if (
                dropin.is_symlink()
                or hashlib.sha256(dropin.read_bytes()).digest()
                != hashlib.sha256(network.encode()).digest()
            ):
                raise ValueError("E_TEST_DROPIN_CHANGED")
            dropin.unlink()
            dropin.parent.rmdir()
            systemctl("daemon-reload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    args = parser.parse_args()
    result = exercise(args.root, args.worker)
    with (args.root / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
