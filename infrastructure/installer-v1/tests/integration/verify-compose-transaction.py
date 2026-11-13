"""Actual local Compose transaction in an explicitly scoped disposable worker.

Loopback eligibility, absent systemd probes and global foreign-installation
discovery are explicitly injected. Foreign containers remain untouched.
Docker, Core, Web, TLS, GPG, PG snapshots, Flyway and recovery execute normally.
The host launcher must bind this worker's private root at the same daemon path.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import runpy
import secrets
import shutil
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import host
import runtime
import update_transaction
from bundle import authenticated_review, sha256
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from docker_images import scrub_names
from onboarding import CoreClient
from recovery import load_installation
from release_channel import stamp
from update_compose import Compose


def docker(*arguments, timeout=600):
    process = subprocess.run(
        ["docker", *arguments], capture_output=True, check=False, timeout=timeout
    )
    if process.returncode:
        raise ValueError("E_FIXTURE_COMPOSE_DOCKER")
    return process.stdout


def vendor(reference):
    index = json.loads(docker("buildx", "imagetools", "inspect", "--raw", reference))
    descriptors = [
        item
        for item in index["manifests"]
        if item.get("platform", {}).get("os") == "linux"
        and item.get("platform", {}).get("architecture") == "amd64"
    ]
    if len(descriptors) != 1:
        raise ValueError("E_FIXTURE_VENDOR_PLATFORM")
    # Pull by immutable digest; never replace the developer's vendor tag.
    selected = reference.split(":", 1)[0] + "@" + descriptors[0]["digest"]
    docker("pull", "--platform", "linux/amd64", selected)
    return selected


def export(directory, name, image, expected):
    original = directory / (name + ".original")
    docker("image", "save", "--output", str(original), image)
    archive = directory / name
    try:
        with (
            tarfile.open(original, "r|") as source,
            tarfile.open(archive, "w") as target,
        ):
            for entry in source:
                if entry.name == "manifest.json":
                    value = json.load(source.extractfile(entry))
                    if len(value) != 1:
                        raise ValueError("E_FIXTURE_IMAGE_COUNT")
                    value[0]["RepoTags"] = [expected]
                    raw = json.dumps(value).encode()
                elif entry.name in {"index.json", "repositories"}:
                    raw = scrub_names(entry.name, source.extractfile(entry).read())
                else:
                    target.addfile(
                        entry, source.extractfile(entry) if entry.isfile() else None
                    )
                    continue
                entry.size = len(raw)
                target.addfile(entry, io.BytesIO(raw))
    finally:
        original.unlink(missing_ok=True)
    return {"name": name, "bytes": archive.stat().st_size, "sha256": sha256(archive)}


def bundle(parent, images, release):
    directory = parent / release
    directory.mkdir(mode=0o700)
    artifacts = []
    for role, image in images.items():
        name = ("kyrion-" if role in {"core", "web"} else "") + role + "-amd64.tar"
        expected = {
            "postgres": "postgres:17.6-alpine",
            "caddy": "caddy:2.10.2-alpine",
        }.get(role, "kyrion/" + role + ":" + release)
        artifacts.append(export(directory, name, image, expected))
    raw = json.dumps(
        {
            "schemaVersion": 1,
            "release": release,
            "architecture": "linux/amd64",
            "artifacts": artifacts,
        },
        separators=(",", ":"),
    ).encode()
    (directory / "manifest.json").write_bytes(raw)
    private = Ed25519PrivateKey.generate()
    public = directory / "public.pem"
    public.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    (directory / "manifest.sig").write_bytes(private.sign(raw))
    return directory, public, authenticated_review(directory, public)


def exercise(root, specification):
    identifier = specification["id"]
    uuid.UUID(hex=identifier)
    run_id = uuid.UUID(hex=specification["runId"]).hex
    if (
        specification.get("scope") != "installer-compose-fixture"
        or root != Path("/var/lib/installer-fixtures") / run_id
        or not Path("/.dockerenv").exists()
        or os.geteuid() != 0
        or os.environ.get("KYRION_COMPOSE_FIXTURE") != identifier
        or json.loads((root / "fixture.json").read_bytes())
        != {"scope": "installer-compose-fixture", "id": identifier}
    ):
        raise ValueError("E_FIXTURE_SCOPE")
    foreign = set(docker("ps", "-aq").decode().split())
    if shutil.disk_usage(root).free < 12 * 1024**3:
        raise ValueError("E_FIXTURE_DISK")
    for image in specification["images"].values():
        actual = json.loads(docker("image", "inspect", image["tag"]))[0]
        if (
            actual["Id"] != image["id"]
            or actual["Config"]["Labels"].get("kyrion.fixture.scope") != identifier
        ):
            raise ValueError("E_FIXTURE_APPLICATION_IMAGE_CHANGED")
    shared = {
        "postgres": vendor("postgres:17.6-alpine"),
        "caddy": vendor("caddy:2.10.2-alpine"),
        "web": specification["images"]["web"]["id"],
    }
    source, key, reviewed = bundle(
        root, {**shared, "core": specification["images"]["core-source"]["id"]}, "1.0.1"
    )
    target, _, newer = bundle(
        root, {**shared, "core": specification["images"]["core-target"]["id"]}, "1.0.2"
    )
    print("fixture: signed source and migration bundles verified", flush=True)
    # The source driver and actual frozen worker use an isolated public channel.
    channel_key = Ed25519PrivateKey.generate().public_key()
    import time

    trust = {
        "formatVersion": 1,
        "epoch": 1,
        "keys": [
            {
                "id": "fixture",
                "pem": channel_key.public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode(),
                "notBefore": int(time.time()) - 60,
                "notAfter": int(time.time()) + 86400,
                "usages": ["release-index", "trust-rotation"],
            }
        ],
    }
    channel = root / "public-channel.json"
    channel.write_text(
        json.dumps(
            {
                "formatVersion": 1,
                "feed": "https://synthetic.example.test/index.json",
                "trust": trust,
            }
        )
    )
    stamp(ROOT, "1.0.0", channel)
    sys.path.insert(0, str(ROOT / "release"))
    build = runpy.run_path(str(ROOT / "release/build-native.py"))["build"]
    frozen = build(root / "worker-build", "1.0.0", channel)
    print("fixture: native maintenance worker built and probed", flush=True)
    worker = root / "worker"
    with tarfile.open(frozen) as package:
        raw_worker = package.extractfile("kyrion-installer").read()
    worker.write_bytes(raw_worker)
    worker.chmod(0o700)
    target_root = root / "installed"
    network_check = runtime.validate_network
    command = host.command
    execute = runtime.execute

    def prerequisites(arguments, *args, **kwargs):
        if (
            arguments[:2] in (["systemctl", "is-active"], ["systemctl", "is-enabled"])
            and arguments[-1] == "docker"
        ):
            return "active" if arguments[1] == "is-active" else "enabled"
        return command(arguments, *args, **kwargs)

    def scoped_discovery(arguments, *args, **kwargs):
        if arguments == ["docker", "ps", "-a", "--format", "{{.Image}} {{.Names}}"]:
            # A shared developer daemon already contains unrelated installations.
            # Their state is not this fixture's fresh-install acceptance surface.
            # Production discovery is unchanged; actual collision/port checks,
            # immutable image loading and every project operation still execute.
            return ""
        return execute(arguments, *args, **kwargs)

    # These are explicit fixture prerequisite substitutions, not success mocks.
    with (
        patch(
            "runtime.validate_network",
            side_effect=lambda hostname, address: network_check(
                hostname, address, allow_loopback=True
            ),
        ),
        patch("host.command", side_effect=prerequisites),
        patch("runtime.execute", side_effect=scoped_discovery),
    ):
        state = runtime.provision(
            target_root,
            source,
            key,
            "fixture.test",
            "127.0.0.1",
            reviewed.manifest_sha256,
        )
        repeated = runtime.provision(
            target_root,
            source,
            key,
            "fixture.test",
            "127.0.0.1",
            reviewed.manifest_sha256,
        )
        if state["installationId"] != repeated["installationId"]:
            raise ValueError("E_FIXTURE_REPEAT_IDENTITY")
    print("fixture: actual fresh and repeated installation healthy", flush=True)
    installation = load_installation(target_root)
    client = CoreClient(installation)
    credentials = {"username": "compose-owner", "password": secrets.token_urlsafe(32)}
    owner = client.request(
        "POST",
        "/v1/auth/setup",
        {
            **credentials,
            "spaceType": "BUSINESS",
            "spaceName": "Synthetic Compose fixture",
        },
        bootstrap=(target_root / "secrets/bootstrap.secret").read_text().strip(),
    )
    client.session = owner["sessionToken"]
    identity = client.request("GET", "/v1/auth/me")
    print("fixture: actual local owner and BUSINESS Space authenticated", flush=True)
    knowledge = target_root / "data/knowledge/fixture.txt"
    knowledge.write_text("Original fixture knowledge\n")
    # Emulate an existing installation from before immutable Compose pins. No
    # shared engine tags are created/moved; existing containers retain their
    # actual source IDs, which must replace these legacy references before stop.
    legacy_compose = (ROOT / "templates/compose.yml").read_bytes()
    (target_root / "compose.yml").write_bytes(legacy_compose)
    installation.state["files"]["compose.yml"] = sha256(target_root / "compose.yml")
    installation.state.pop("runtimeImageIds", None)
    installation.save()
    helper = runpy.run_path(
        str(Path(__file__).with_name("verify-update-transaction.py")),
        run_name="compose_proof_helpers",
    )
    helper["signed_inputs"](installation, target, newer)
    name = "maintenance-" + sha256(worker)[:32]
    installation.write(name, raw_worker)
    (target_root / name).chmod(0o700)
    installation.state["updatePolicy"]["workerFile"] = name
    installation.save()
    original = Compose(installation).identity()
    password = secrets.token_urlsafe(40)

    def interrupted(_adapter):
        raise KeyboardInterrupt("Synthetic loss before application activation")

    try:
        with patch.object(Compose, "activate", interrupted):
            update_transaction.apply(target_root, password, review=lambda _: True)
    except KeyboardInterrupt:
        pass
    else:
        raise ValueError("E_FIXTURE_INTERRUPTION_MISSING")
    if (
        load_installation(target_root, verify=False).state["updateTransaction"]["phase"]
        != "activating"
    ):
        raise ValueError("E_FIXTURE_ACTIVATION_CHECKPOINT")
    update_transaction.resume(target_root, password)
    print(
        "fixture: encrypted backup, migration and activation resume completed",
        flush=True,
    )
    installed = load_installation(target_root)
    transaction = installed.state["updateTransaction"]
    if (
        transaction["sourceAliases"].get("compose.yml")
        != hashlib.sha256(legacy_compose).hexdigest()
        or (target_root / transaction["directory"] / "original-compose").read_bytes()
        != legacy_compose
        or installed.state["runtimeImageIds"] != transaction["targetImages"]
    ):
        raise ValueError("E_FIXTURE_SOURCE_PIN_RECONCILIATION")
    adapter = Compose(installed)
    if adapter.schema() != 50 or adapter.identity() != original:
        raise ValueError("E_FIXTURE_MIGRATION_IDENTITY")
    adapter.query("INSERT INTO installer_update_probe VALUES(2)")
    knowledge.write_text("Post activation fixture knowledge\n")
    try:
        update_transaction.recover(target_root, password)
    except ValueError as error:
        if str(error) != "E_UPDATE_RECOVERY_WRITES_ACK_REQUIRED":
            raise
    else:
        raise ValueError("E_FIXTURE_RECOVERY_ACK_MISSING")
    result = update_transaction.recover(target_root, password, acknowledge_writes=True)
    print("fixture: acknowledged recovery completed", flush=True)
    restored = load_installation(target_root)
    adapter = Compose(restored)
    if (
        adapter.schema() != 49
        or adapter.identity() != original
        or knowledge.read_text() != "Original fixture knowledge\n"
        or restored.state["runtimeImageIds"] != transaction["original"]["images"]
    ):
        raise ValueError("E_FIXTURE_RECOVERY_DATA")
    client = CoreClient(restored)
    client.session = client.request("POST", "/v1/auth/login", credentials)[
        "sessionToken"
    ]
    if (
        client.request("GET", "/v1/auth/me")["id"] != identity["id"]
        or not result["recovered"]
    ):
        raise ValueError("E_FIXTURE_RECOVERY_LOGIN")
    if not foreign <= set(docker("ps", "-aq").decode().split()):
        raise ValueError("E_FIXTURE_FOREIGN_CONTAINER_MISSING")
    return {
        "actualDockerCompose": True,
        "freshAndRepeatedInstallation": True,
        "actualCoreAndWebTlsHealth": True,
        "encryptedBackupAndPostActivationBackup": True,
        "actualFlyway49To50": True,
        "interruptedActivationResumed": True,
        "legacyTaggedSourceRecoveredByImmutableIds": True,
        "actualDatabaseAndKnowledgeRecovery": True,
        "localOwnerIdentityPreservedAfterRecovery": True,
        "loopbackEligibilityInjected": True,
        "systemdPrerequisitesInjected": True,
        "foreignInstallationDiscoveryInjected": True,
        "preexistingContainersPreserved": True,
        "systemdOrColdBootAccepted": False,
        "actualBrowserSsoAccepted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--specification", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = exercise(args.root, json.loads(args.specification.read_bytes()))
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
