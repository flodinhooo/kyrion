"""Actual Docker/OCI import using two tiny owned scratch images; never run them."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from docker_images import archive_references, load_untagged
from host import reject_links
from runtime import image_identity


def verify(docker: Path, work: Path) -> dict:
    identifier = uuid.uuid4().hex
    root = work / ("image-import-" + identifier)
    reject_links(root)
    root.mkdir(mode=0o700)
    tags = [
        "installer-image-fixture-" + identifier + ":" + variant
        for variant in ("source", "other")
    ]

    def run(*arguments, timeout=180):
        result = subprocess.run(
            [str(docker), "--context", "default", *arguments],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        if result.returncode or len(result.stdout) > 4 * 1024**2:
            raise ValueError("E_FIXTURE_DOCKER_IMAGE_OPERATION")
        return result.stdout

    if run("info", "--format", "{{.OSType}}").strip() != b"linux":
        raise ValueError("E_FIXTURE_LINUX_ENGINE_REQUIRED")
    builder = run("buildx", "inspect", "default").decode()
    if not re.search(r"^Driver:\s+docker\s*$", builder, re.MULTILINE):
        raise ValueError("E_FIXTURE_LOCAL_BUILDER_REQUIRED")
    endpoint = json.loads(run("context", "inspect", "default"))[0]["Endpoints"][
        "docker"
    ]["Host"]
    if not endpoint.startswith(("npipe:////./pipe/", "unix://")):
        raise ValueError("E_FIXTURE_LOCAL_BUILDER_REQUIRED")
    identities = []
    container = "installer-image-witness-" + identifier
    created = False
    try:
        for tag, variant in zip(tags, ("A", "B"), strict=True):
            if run(
                "image", "ls", "--format", "{{.ID}}", "--filter", "reference=" + tag
            ).strip():
                raise ValueError("E_FIXTURE_IMAGE_ALREADY_EXISTS")
            directory = root / variant
            directory.mkdir()
            (directory / "payload.txt").write_text("Synthetic fixture " + variant)
            (directory / "Dockerfile").write_text(
                'FROM scratch\nLABEL kyrion.fixture.scope="'
                + identifier
                + '"\nCOPY payload.txt /synthetic.txt\n'
            )
            run(
                "buildx",
                "build",
                "--builder",
                "default",
                "--load",
                "--network",
                "none",
                "--platform",
                "linux/amd64",
                "--tag",
                tag,
                str(directory),
                timeout=180,
            )
            identities.append(
                run("image", "inspect", "--format", "{{.Id}}", tag).decode().strip()
            )
        archive = root / "source.tar"
        run("image", "save", "--output", str(archive), tags[0])
        (root / "identity-witness.json").write_text(
            json.dumps(
                {
                    "engineImageId": identities[0],
                    "archiveConfigurationId": image_identity(archive, tags[0]),
                }
            ),
            encoding="utf-8",
        )
        configuration = image_identity(archive, tags[0])
        if identities[0] not in archive_references(archive, configuration, "amd64"):
            raise ValueError("E_FIXTURE_IMAGE_ARCHIVE_IDENTITY")
        # Simulate a shared name moving after the original archive was made.
        # Both names/images here are exclusively created by this fixture.
        run("image", "tag", tags[1], tags[0])
        loaded = load_untagged(root, archive, configuration, "amd64", run)
        if loaded != identities[0]:
            raise ValueError("E_FIXTURE_LOADED_IMAGE_IDENTITY")
        # The update adapter records Container.Image, which can differ from
        # image-inspect Id on engines backed by containerd. Check the exact
        # source identity used by retention/recovery without executing a process.
        run(
            "create",
            "--name",
            container,
            "--label",
            "kyrion.fixture.scope=" + identifier,
            "--network",
            "none",
            "--read-only",
            "--entrypoint",
            "/never-executed",
            loaded,
        )
        created = True
        witness = json.loads(run("container", "inspect", container))[0]
        source = witness["Image"]
        if witness["State"]["Running"] or source not in archive_references(
            archive, configuration, "amd64"
        ):
            raise ValueError("E_FIXTURE_CONTAINER_IMAGE_IDENTITY")
        pinned = json.loads(run("image", "inspect", source))[0]
        if pinned["Id"] not in archive_references(archive, configuration, "amd64"):
            raise ValueError("E_FIXTURE_SOURCE_PIN_NOT_RESOLVABLE")
        if (
            run("image", "inspect", "--format", "{{.Id}}", tags[0]).decode().strip()
            != identities[1]
        ):
            raise ValueError("E_FIXTURE_SHARED_IMAGE_TAG_CHANGED")
        return {
            "actualLinuxDockerImageImport": True,
            "originalArchiveIdentityValidated": True,
            "sharedTagPreserved": True,
            "configurationAndEngineIdentityBound": True,
            "actualContainerSourcePinResolvable": True,
            "containerImageAndInspectIdEqual": source == loaded,
            "scratchImagesExecuted": False,
            "unstartedDisposableContainerCreated": True,
            "servicesInstalled": False,
            "osOrColdBootAccepted": False,
        }
    finally:
        if created:
            witness = json.loads(run("container", "inspect", container))[0]
            if (
                witness["Config"]["Labels"].get("kyrion.fixture.scope") != identifier
                or witness["State"]["Running"]
            ):
                raise ValueError("E_FIXTURE_CONTAINER_CLEANUP_OWNER")
            run("container", "rm", container)
        for tag in tags:
            rows = run(
                "image", "ls", "--format", "{{.ID}}", "--filter", "reference=" + tag
            ).strip()
            if not rows:
                continue
            labels = json.loads(
                run("image", "inspect", "--format", "{{json .Config.Labels}}", tag)
            )
            if labels.get("kyrion.fixture.scope") != identifier:
                raise ValueError("E_FIXTURE_IMAGE_CLEANUP_OWNER")
            # Remove only our exact references; never force-delete an image or
            # prune shared content. An untagged cached scratch layer is harmless.
            run("image", "rm", "--no-prune", tag)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.docker.resolve(), args.work.resolve())
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
