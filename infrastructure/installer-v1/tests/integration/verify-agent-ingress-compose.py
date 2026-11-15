"""Actual managed Compose/Core/PG/Web/Caddy transition with controlled interruptions."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import secrets
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import node_ingress
from authority import require_active
from bundle import sha256
from node_pairing import guided_export
from onboarding import CoreClient
from recovery import load_installation
from runtime import Installation, installation_lock


def containers(installation) -> dict[str, str]:
    raw = installation.compose("ps", "--all", "--format", "json").strip()
    value = (
        json.loads(raw)
        if raw.startswith("[")
        else [json.loads(line) for line in raw.splitlines()]
    )
    if isinstance(value, dict):
        value = [value]
    return {row["Service"]: row["ID"] for row in value}


def legacy(installation):
    runtime = node_ingress.ComposeRuntime(installation)
    runtime.stop()
    text = next(
        value
        for value in node_ingress.definitions(installation)[1]
        if "@kyrion_agent" not in value
    )
    path = installation.target / node_ingress.FILE
    path.write_bytes(text.encode())
    path.chmod(0o600)
    installation.state["files"][node_ingress.FILE] = node_ingress.digest(text)
    installation.state.pop(node_ingress.KEY, None)
    installation.save()
    runtime.start()
    return text


def exercise(args):
    if os.geteuid() != 0 or not sys.platform.startswith("linux"):
        raise ValueError("E_FIXTURE_ROOT_LINUX_REQUIRED")
    from update_worker import validate_host

    validate_host(args.work)
    plan = json.loads(args.image_plan.read_bytes())
    if plan.get("scope") != "installer-agent-ingress-development-images":
        raise ValueError("E_FIXTURE_IMAGE_SCOPE")
    if not re.fullmatch(r"[a-f0-9]{64}", plan.get("coreJarSha256", "")):
        raise ValueError("E_FIXTURE_CORE_IDENTITY")
    if set(plan["images"]) != {"core", "web", "postgres", "caddy"} or any(
        not re.fullmatch(r"sha256:[a-f0-9]{64}", value)
        for value in plan["images"].values()
    ):
        raise ValueError("E_FIXTURE_IMAGE_IDENTITY")
    addresses = json.loads(
        subprocess.check_output(["/usr/sbin/ip", "-json", "address"])
    )
    if "10.231.0.1" not in {
        item["local"] for interface in addresses for item in interface["addr_info"]
    }:
        raise ValueError("E_FIXTURE_NETWORK")
    routes = json.loads(subprocess.check_output(["/usr/sbin/ip", "-json", "route"]))
    if any(row.get("dst") == "default" for row in routes):
        raise ValueError("E_FIXTURE_DEFAULT_ROUTE")
    root = args.work / ("agent-ingress-" + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    (root / "fixture.json").write_text(
        json.dumps({"scope": "installer-agent-ingress-compose-fixture"}),
        encoding="utf-8",
    )
    manifest = {"release": "0.0.0-dev.ingress-fixture", "architecture": "linux/amd64"}
    installation = Installation(
        root / "installed",
        manifest,
        hashlib.sha256(args.image_plan.read_bytes()).hexdigest(),
        "fixture.test",
        "10.231.0.1",
    )
    installation.state["runtimeImageIds"] = plan["images"]
    installation.save()
    client = CoreClient(installation)
    capture = io.StringIO()
    try:
        installation.configure(images=plan["images"])
        legacy_text = legacy(installation)
        installation.start()
        original_ids = containers(installation)
        snapshot = {
            name: installation.state["files"][name]
            for name in (
                "data/tls/cert.pem",
                "data/tls/key.pem",
                "secrets/credential.key",
                "secrets/audit-integrity.key",
            )
        }
        setup = client.request(
            "POST",
            "/v1/auth/setup",
            {
                "username": "ingress-fixture",
                "password": secrets.token_urlsafe(32),
                "spaceType": "HOME",
                "spaceName": "Ingress fixture",
            },
            bootstrap=(installation.target / "secrets/bootstrap.secret")
            .read_text()
            .strip(),
        )
        client.session = setup["sessionToken"]
        identity = client.request("GET", "/v1/auth/me")
        messages = json.loads((ROOT / "locales/en.json").read_text(encoding="utf-8"))
        with (
            installation_lock(installation.target),
            patch(
                "builtins.input",
                side_effect=[
                    "Prepared fixture node",
                    "PAIR",
                    "ENABLE-AGENT-INGRESS",
                ],
            ),
            contextlib.redirect_stdout(capture),
        ):
            guided_export(client, messages)
        if installation.state[node_ingress.KEY]["phase"] != "verified":
            raise ValueError("E_FIXTURE_INGRESS_NOT_VERIFIED")
        changed_ids = containers(installation)
        if changed_ids["caddy"] == original_ids["caddy"] or any(
            changed_ids[role] != original_ids[role]
            for role in ("core", "web", "postgres")
        ):
            raise ValueError("E_FIXTURE_RESTART_SCOPE")
        transfers = list(installation.target.glob("pairing-transfer-*/pairing.json"))
        if len(transfers) != 1:
            raise ValueError("E_FIXTURE_TRANSFER_AFTER_EXTENSION")
        transfer = json.loads(transfers[0].read_bytes())
        if (
            transfer["enrollmentToken"] in capture.getvalue()
            or client.session in capture.getvalue()
        ):
            raise ValueError("E_FIXTURE_SECRET_OUTPUT")
        if client.request("GET", "/v1/auth/me")["id"] != identity["id"]:
            raise ValueError("E_FIXTURE_USER_CHANGED")
        schema = installation.compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "kyrion",
            "-d",
            "kyrion",
            "-Atc",
            "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version IS NOT NULL",
        ).strip()
        if schema != "51":
            raise ValueError("E_FIXTURE_SCHEMA")

        legacy(installation)
        checkpoint = node_ingress.checkpoint

        def interrupted(installation, phase):
            if phase == "published":
                raise KeyboardInterrupt
            checkpoint(installation, phase)

        with (
            installation_lock(installation.target),
            patch.object(node_ingress, "checkpoint", side_effect=interrupted),
        ):
            try:
                node_ingress.apply(
                    installation, node_ingress.actor(client), "configure"
                )
            except KeyboardInterrupt:
                pass
            else:
                raise ValueError("E_FIXTURE_INTERRUPTION_NOT_REACHED")
        try:
            load_installation(installation.target)
        except ValueError as error:
            if str(error) != "E_AGENT_INGRESS_PENDING":
                raise
        else:
            raise ValueError("E_FIXTURE_UNFENCED_PENDING_INGRESS")
        installation = load_installation(installation.target, verify=False)
        client.installation = installation
        transaction_id = installation.state[node_ingress.KEY]["id"]
        with installation_lock(installation.target):
            node_ingress.apply(installation, node_ingress.actor(client), "resume")
        if installation.state[node_ingress.KEY]["id"] != transaction_id:
            raise ValueError("E_FIXTURE_DUPLICATE_TRANSITION")

        legacy(installation)
        original_probe = node_ingress.ComposeRuntime.probe

        def actual_core_loss(runtime):
            runtime.adapter.compose("stop", "--timeout", "30", "core", timeout=60)
            original_probe(runtime)

        with (
            installation_lock(installation.target),
            patch.object(node_ingress.ComposeRuntime, "probe", actual_core_loss),
        ):
            try:
                node_ingress.apply(
                    installation, node_ingress.actor(client), "configure"
                )
            except RuntimeError:
                pass
            else:
                raise ValueError("E_FIXTURE_UNAVAILABLE_CORE_REPORTED_SUCCESS")
        installation = load_installation(installation.target, verify=False)
        with installation_lock(installation.target):
            result = node_ingress.apply(installation, None, "recover")
        if not result["originalProxyTlsVerified"] or result["agentConnectionVerified"]:
            raise ValueError("E_FIXTURE_RECOVERY_READINESS_OVERCLAIM")
        if (installation.target / node_ingress.FILE).read_text() != legacy_text:
            raise ValueError("E_FIXTURE_ORIGINAL_CONFIGURATION_NOT_RESTORED")
        require_active(installation.state)
        installation.compose(
            "up",
            "-d",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "120",
            "core",
            timeout=150,
        )
        installation.check_health()
        client.installation = installation
        if client.request("GET", "/v1/auth/me")["id"] != identity["id"]:
            raise ValueError("E_FIXTURE_RECOVERY_IDENTITY_CHANGED")
        if any(
            sha256(installation.target / name) != digest
            for name, digest in snapshot.items()
        ):
            raise ValueError("E_FIXTURE_KEYS_CHANGED")
        return {
            "scope": "installer-agent-ingress-compose-fixture",
            "fixtureRoot": str(root),
            "actualDockerComposeCorePostgreSqlWebCaddy": True,
            "coreJarSha256": plan["coreJarSha256"],
            "actualSchema": 51,
            "actualCorePermissionRead": True,
            "actualCaddyCliValidation": True,
            "actualAtomicConfigurationPublication": True,
            "onlyOwnedProxyRecreated": True,
            "actualPinnedAgentTlsProbe": True,
            "actualPairingExportAfterReviewedExtension": True,
            "interruptionInjectedAfterActualReplace": True,
            "sameTransactionResumed": True,
            "ordinaryOperationsFencedWhilePending": True,
            "actualCoreOutageRecovery": True,
            "originalConfigurationAndTlsRestoredWithoutCore": True,
            "identityAndKeysPreserved": True,
            "imagePlanUsesControlledDevelopmentImages": True,
            "legacyConfigurationReseededBetweenCases": True,
            "terminalChoicesInjected": True,
            "successResponsesMocked": False,
            "actualOperatingSystemServiceStartup": False,
            "actualProviderBrowserLogin": False,
            "networkNamespaceWithoutDefaultRoute": True,
            "realHouseholdActions": False,
        }
    finally:
        client.close()
        marker = json.loads((root / "fixture.json").read_bytes())
        if marker["scope"] != "installer-agent-ingress-compose-fixture":
            raise ValueError("E_FIXTURE_CLEANUP_SCOPE")
        # Exact owned project only; retain all data/images and never prune Docker.
        installation.compose("down", "--timeout", "30", timeout=120)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-plan", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = exercise(args)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
