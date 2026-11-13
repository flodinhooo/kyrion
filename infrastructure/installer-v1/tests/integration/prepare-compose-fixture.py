"""Build real application images in a scoped, local-only Docker fixture.

No registry publication, host service installation or global image cleanup.
Only tracked public Web sources and explicitly selected built JARs are copied.
The target JAR adds a synthetic V50 migration to exercise actual Flyway.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path


def prepare(docker: Path, repository: Path, work: Path, core: Path, parser: Path):
    identifier = uuid.uuid4().hex
    root = work / ("compose-fixture-" + identifier)
    root.mkdir(mode=0o700)

    def run(*arguments, timeout=120):
        result = subprocess.run(
            [str(docker), "--context", "default", *arguments],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise ValueError("E_FIXTURE_DOCKER_BUILD")
        return result.stdout

    endpoint = json.loads(run("context", "inspect", "default"))[0]["Endpoints"][
        "docker"
    ]["Host"]
    if (
        not endpoint.startswith(("unix://", "npipe:////./pipe/"))
        or run("info", "--format", "{{.OSType}}").strip() != b"linux"
        or not re.search(
            r"^Driver:\s+docker\s*$",
            run("buildx", "inspect", "default").decode(),
            re.MULTILINE,
        )
    ):
        raise ValueError("E_FIXTURE_LOCAL_LINUX_BUILDER_REQUIRED")
    if shutil.disk_usage(work).free < 12 * 1024**3:
        raise ValueError("E_FIXTURE_BUILD_DISK")
    with core.open("rb") as source_jar:
        source_digest = hashlib.file_digest(source_jar, "sha256").hexdigest()
    fixture = {
        "formatVersion": 1,
        "scope": "installer-compose-fixture",
        "id": identifier,
        "sourceJarSha256": source_digest,
        "images": {},
        "acceptance": False,
    }
    witness = root / "fixture.json"
    witness.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")

    def build(role, directory):
        tag = "installer-compose-fixture-" + identifier + ":" + role
        if run(
            "image", "ls", "--filter", "reference=" + tag, "--format", "{{.ID}}"
        ).strip():
            raise ValueError("E_FIXTURE_IMAGE_EXISTS")
        log = root / (role + "-build.log")
        with log.open("xb") as stream:
            result = subprocess.run(
                [
                    str(docker),
                    "--context",
                    "default",
                    "buildx",
                    "build",
                    "--builder",
                    "default",
                    "--load",
                    "--platform",
                    "linux/amd64",
                    "--label",
                    "kyrion.fixture.scope=" + identifier,
                    "--tag",
                    tag,
                    str(directory),
                ],
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=1800,
                check=False,
            )
        if result.returncode:
            raise ValueError("E_FIXTURE_BUILD_" + role.upper())
        image = json.loads(run("image", "inspect", tag))[0]
        if image["Config"]["Labels"].get("kyrion.fixture.scope") != identifier:
            raise ValueError("E_FIXTURE_IMAGE_OWNER")
        fixture["images"][role] = {"tag": tag, "id": image["Id"]}
        witness.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")

    public = root / "web"
    public.mkdir()
    tracked = (
        subprocess.run(
            [
                "git",
                "-c",
                "safe.directory=" + repository.as_posix(),
                "ls-files",
                "-z",
                "--",
                "apps/web",
            ],
            cwd=repository,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    records = {}
    for name in tracked:
        if not name:
            continue
        relative = Path(name).relative_to("apps/web")
        if any(
            part.startswith(".env") or part in {"node_modules", ".next", ".git"}
            for part in relative.parts
        ):
            continue
        source = repository / name
        if (
            not source.is_file()
            or source.is_symlink()
            or source.stat().st_size > 32 * 1024**2
        ):
            raise ValueError("E_FIXTURE_PUBLIC_SOURCE")
        target = public / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        target.write_bytes(raw)
        records[relative.as_posix()] = hashlib.sha256(raw).hexdigest()
    (root / "public-web-source.json").write_text(
        json.dumps(records, sort_keys=True), encoding="utf-8"
    )
    for role in ("core-source", "core-target"):
        directory = root / role
        directory.mkdir()
        shutil.copyfile(core, directory / "app.jar")
        shutil.copyfile(parser, directory / "knowledge-parser.jar")
        if role == "core-target":
            with zipfile.ZipFile(directory / "app.jar", "a") as package:
                migration = (
                    "BOOT-INF/classes/db/migration/V50__installer_compose_fixture.sql"
                )
                if migration in package.namelist() or any(
                    re.search(r"/V(?:5\d|[6-9]\d|\d{3,})__", name)
                    for name in package.namelist()
                ):
                    raise ValueError("E_FIXTURE_SOURCE_SCHEMA")
                package.writestr(
                    migration,
                    "CREATE TABLE installer_update_probe(id integer PRIMARY KEY); INSERT INTO installer_update_probe VALUES(1);",
                )
        (directory / "Dockerfile").write_text(
            "FROM eclipse-temurin:21-jre-jammy\n"
            "RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*\n"
            "RUN groupadd --gid 10001 kyrion && useradd --uid 10001 --gid 10001 --no-create-home kyrion\n"
            "WORKDIR /opt/kyrion\nCOPY app.jar app.jar\nCOPY knowledge-parser.jar knowledge-parser.jar\n"
            "ENV KYRION_KNOWLEDGE_PARSER_JAR=/opt/kyrion/knowledge-parser.jar KYRION_KNOWLEDGE_ROOT=/var/lib/kyrion/knowledge\n"
            'USER 10001:10001\nEXPOSE 8080\nENTRYPOINT ["java","-jar","/opt/kyrion/app.jar"]\n',
            encoding="utf-8",
        )
        build(role, directory)
    build("web", public)
    return witness


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description=__doc__)
    for option in ("docker", "repository", "work", "core-jar", "parser-jar"):
        arguments.add_argument("--" + option, type=Path, required=True)
    args = arguments.parse_args()
    print(
        prepare(
            args.docker.resolve(),
            args.repository.resolve(),
            args.work.resolve(),
            args.core_jar.resolve(),
            args.parser_jar.resolve(),
        )
    )
