"""Local rootful Docker update adapter with pinned, retained image identities."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from bundle import sha256
from host import reject_links
from portable_database import capture as capture_rows
from recovery import private_restore_directory
from runtime import image_identity, image_plan, startup_overrides
from update_native import LAUNCHER, MAIN
from update_state import path, transaction


class Compose:
    gpg = None
    environment = None

    def __init__(self, installation):
        if installation.state.get("startupPolicy") is not None:
            from linux_startup import require_bound

            require_bound(installation)
        self.installation = installation
        self.root = installation.target
        self.backup_manifest = None
        executable = shutil.which("docker")
        if executable is None:
            raise ValueError("E_RUNTIME")
        self.docker = Path(executable).resolve()
        for item in (self.docker, *self.docker.parents):
            if item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
                raise ValueError("E_UPDATE_DOCKER_OWNER")
        self.env = {"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": "/root"}
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"):
            if os.environ.get(key):
                self.env[key] = os.environ[key]
        config = Path(self.env.get("DOCKER_CONFIG", "/root/.docker"))
        if config.exists():
            reject_links(config)
            for item in (config, *config.parents):
                if item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
                    raise ValueError("E_UPDATE_DOCKER_OWNER")
        context = self.run("context", "show").decode().strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", context):
            raise ValueError("E_UPDATE_DOCKER_LOCAL_REQUIRED")
        info = json.loads(self.run("context", "inspect", context))
        endpoints = [info[0]["Endpoints"]["docker"]["Host"]]
        if self.env.get("DOCKER_HOST"):
            endpoints.append(self.env["DOCKER_HOST"])
        sockets = set()
        for endpoint in endpoints:
            parsed = urlsplit(endpoint)
            if (
                parsed.scheme != "unix"
                or parsed.netloc
                or not parsed.path.startswith("/")
            ):
                raise ValueError("E_UPDATE_DOCKER_LOCAL_REQUIRED")
            socket = Path(parsed.path).resolve()
            for parent in socket.parents:
                if parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
                    raise ValueError("E_UPDATE_DOCKER_OWNER")
            if (
                not stat.S_ISSOCK(socket.stat().st_mode)
                or socket.stat().st_uid != 0
                or socket.stat().st_mode & 0o002
            ):
                raise ValueError("E_UPDATE_DOCKER_LOCAL_REQUIRED")
            sockets.add(str(socket))
        self.bind_daemon(sorted(sockets))
        if (
            installation.state.get("startupPolicy") is not None
            and installation.state["startupPolicy"]["daemon"] != self.daemon
        ):
            raise ValueError("E_STARTUP_DOCKER_CHANGED")

    def bind_daemon(self, sockets: list[str]) -> None:
        identifier = self.run("info", "--format", "{{.ID}}").decode().strip()
        if not re.fullmatch(r"[A-Za-z0-9:._-]{8,128}", identifier):
            raise ValueError("E_UPDATE_DOCKER_IDENTITY")
        self.daemon = {"id": identifier, "sockets": sockets}
        previous = self.installation.state.get("updateTransaction")
        if (
            previous is not None
            and previous.get("original", {}).get("daemon") != self.daemon
        ):
            raise ValueError("E_UPDATE_DOCKER_CHANGED")

    def run(self, *arguments, output=None, timeout=180) -> bytes:
        result = subprocess.run(
            [str(self.docker), *arguments],
            cwd=self.root,
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=output or subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        if result.returncode or (output is None and len(result.stdout) > 8 * 1024**2):
            raise ValueError("E_UPDATE_DOCKER")
        return result.stdout or b""

    def compose(self, *arguments, maintenance=False, output=None, timeout=180):
        flags = [
            "compose",
            "--project-name",
            "kyrion-" + self.installation.state["installationId"],
            "--env-file",
            str(self.root / ".env"),
            "-f",
            str(self.root / "compose.yml"),
            *startup_overrides(self.installation),
        ]
        if maintenance:
            flags += ["-f", str(path(self.installation, "maintenance.yml"))]
        return self.run(*flags, *arguments, output=output, timeout=timeout)

    def query(self, sql, *, database="kyrion"):
        if database != "postgres":
            from update_database import sql_name

            sql_name(database)
        return self.compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-X",
            "-U",
            "kyrion",
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-Atc",
            sql,
        )

    def schema(self):
        return int(
            self.query(
                "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'"
            ).strip()
        )

    def identity(self) -> dict[str, str]:
        from update_database import identity

        return identity(self)

    def original(self):
        images = {}
        for role in ("postgres", "core", "web", "caddy"):
            identifier = self.compose("ps", "--all", "-q", role).decode().strip()
            if not re.fullmatch(r"[a-f0-9]{12,64}", identifier):
                raise ValueError("E_UPDATE_SOURCE_COMPONENTS")
            container = json.loads(self.run("inspect", identifier))[0]
            labels = container["Config"]["Labels"]
            if (
                labels.get("com.docker.compose.project")
                != "kyrion-" + self.installation.state["installationId"]
                or labels.get("com.docker.compose.service") != role
            ):
                raise ValueError("E_UPDATE_SOURCE_COMPONENTS")
            image = container["Image"]
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
                raise ValueError("E_IMAGE_PIN")
            images[role] = image
            if role == "postgres" and not any(
                mount.get("Type") == "bind"
                and mount.get("Destination") == "/var/lib/postgresql/data"
                and Path(mount.get("Source", "")).resolve()
                == (self.root / "data/postgres").resolve()
                for mount in container["Mounts"]
            ):
                raise ValueError("E_UPDATE_DATABASE_TARGET")
        return {
            "images": images,
            "daemon": self.daemon,
            "postgresVersion": int(self.query("SHOW server_version_num")),
            "databaseBytes": int(self.query("SELECT pg_database_size('kyrion')")),
        }

    def load_untagged(self, archive: Path, expected: str):
        from docker_images import load_untagged

        return load_untagged(
            self.root,
            archive,
            expected,
            self.installation.configuration["architecture"].split("/")[1],
            self.run,
        )

    def stage(self, reviewed, directory, identifier, original):
        images = {}
        for filename, tag in image_plan(reviewed.manifest).items():
            role = next(
                role
                for role in ("core", "web", "postgres", "caddy")
                if filename.startswith(("kyrion-" + role + "-", role + "-"))
            )
            identity = image_identity(directory / filename, tag)
            images[role] = self.load_untagged(directory / filename, identity)
        self.target_images = images
        version = self.run(
            "run",
            "--pull",
            "never",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "postgres",
            images["postgres"],
            "--version",
        ).decode()
        match = re.search(r"\b(\d+)\.(\d+)\b", version)
        if (
            match is None
            or int(match[1]) * 10000 + int(match[2]) != original["postgresVersion"]
        ):
            raise ValueError("E_UPDATE_POSTGRES_VERSION")
        self.admin("capability", images=images, schema=original["schema"])
        from docker_images import pin_compose

        compose = (self.root / "compose.yml").read_text(encoding="utf-8")
        self.source_configs = {
            "compose.yml": pin_compose(
                compose, original["images"], original["images"]
            ).encode()
        }
        compose = pin_compose(compose, images, original["images"])
        environment = (self.root / ".env").read_text(encoding="utf-8")
        old = "KYRION_RELEASE=" + self.installation.configuration["release"]
        if environment.splitlines().count(old) != 1:
            raise ValueError("E_UPDATE_COMPOSE_LAYOUT")
        environment = environment.replace(
            old + "\n", "KYRION_RELEASE=" + reviewed.manifest["release"] + "\n", 1
        )
        return {".env": environment.encode(), "compose.yml": compose.encode()}

    def retain(self):
        value = transaction(self.installation)
        for role, image in value["original"]["images"].items():
            name = "kyrion-update-" + value["id"] + "-" + role
            existing = (
                self.run(
                    "container",
                    "ls",
                    "--all",
                    "--filter",
                    "name=^/" + name + "$",
                    "--format",
                    "{{.ID}}",
                )
                .decode()
                .strip()
            )
            if existing:
                saved = json.loads(self.run("inspect", existing))[0]
                if (
                    saved["Image"] != image
                    or saved["Config"]["Labels"].get("kyrion.update") != value["id"]
                    or saved["State"]["Running"]
                    or any(mount.get("Type") != "tmpfs" for mount in saved["Mounts"])
                    or saved["HostConfig"]["NetworkMode"] != "none"
                ):
                    raise ValueError("E_UPDATE_IMAGE_RETENTION")
            else:
                flags = (
                    ["--tmpfs", "/var/lib/postgresql/data:ro,noexec,nosuid"]
                    if role == "postgres"
                    else []
                )
                self.run(
                    "create",
                    "--name",
                    name,
                    "--label",
                    "kyrion.update=" + value["id"],
                    "--network",
                    "none",
                    "--read-only",
                    *flags,
                    "--entrypoint",
                    "/bin/true",
                    image,
                )

    def quiesce(self):
        self.compose("stop", "--timeout", "30", "caddy", "web", "core")
        self.ensure_database()

    def ensure_database(self):
        self.compose("up", "-d", "--pull", "never", "--no-deps", "--wait", "postgres")

    def capture(self, destination, password):
        from recovery import capture

        return capture(self.installation, destination, password, update=True)

    def switch(self, kind):
        self.compose("stop", "--timeout", "30", "caddy", "web", "core", "postgres")
        self.ensure_database()

    def admin(self, operation, *, images=None, schema=None):
        if operation == "capability":
            raw = self.run(
                "run",
                "--pull",
                "never",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "java",
                images["core"],
                "-Dloader.main=" + MAIN,
                "-cp",
                "/opt/kyrion/app.jar",
                LAUNCHER,
                "--capability",
            )
            capability = json.loads(raw)
            schemas = capability.get("sourceSchemas")
            if (
                capability.get("formatVersion") != 1
                or capability.get("updateProtocol") != 1
                or capability.get("maintenanceStart") is not True
                or not isinstance(schemas, list)
                or any(type(item) is not int for item in schemas)
                or schema not in schemas
            ):
                raise ValueError("E_UPDATE_CORE_UPGRADE_REQUIRED")
            return
        value = transaction(self.installation)
        # Run the signed target helper without Spring, against the currently
        # selected database, using only existing private read-only secret mounts.
        helper = path(self.installation, "maintenance.yml").with_name("helper.yml")
        relative = helper.relative_to(self.root).as_posix()
        self.installation.write(
            relative,
            "services:\n  core:\n    image: " + value["targetImages"]["core"] + "\n",
        )
        flags = [
            "compose",
            "--project-name",
            "kyrion-" + self.installation.state["installationId"],
            "--env-file",
            str(self.root / ".env"),
            "-f",
            str(self.root / "compose.yml"),
            *startup_overrides(self.installation),
            "-f",
            str(helper),
        ]
        self.run(
            *flags,
            "run",
            "--pull",
            "never",
            "--rm",
            "--no-deps",
            "-T",
            "--entrypoint",
            "java",
            "-e",
            "KYRION_UPDATE_TRANSACTION_ID=" + value["id"],
            "-e",
            "KYRION_UPDATE_EXPECTED_SCHEMA=" + str(schema),
            "core",
            "-Dloader.main=" + MAIN,
            "-cp",
            "/opt/kyrion/app.jar",
            LAUNCHER,
            "--" + operation,
        )

    def maintenance(self):
        self.ensure_database()
        self.compose(
            "up",
            "-d",
            "--pull",
            "never",
            "--no-deps",
            "--wait",
            "core",
            maintenance=True,
        )
        self.check_maintenance()

    def check_maintenance(self):
        health = json.loads(
            self.compose(
                "exec",
                "-T",
                "core",
                "curl",
                "--fail",
                "--silent",
                "--max-time",
                "10",
                "http://127.0.0.1:8080/actuator/health",
            )
        )
        raw = self.compose(
            "exec",
            "-T",
            "core",
            "curl",
            "--silent",
            "--max-time",
            "10",
            "--write-out",
            "\n%{http_code}",
            "http://127.0.0.1:8080/v1/auth/setup/status",
        ).decode()
        body, code = raw.rsplit("\n", 1)
        if (
            health.get("status") != "UP"
            or code != "503"
            or json.loads(body).get("code") != "OPERATIONAL_MAINTENANCE"
        ):
            raise ValueError("E_UPDATE_MAINTENANCE_REQUIRED")

    def stop_application(self):
        self.compose("stop", "--timeout", "30", "caddy", "web", "core")

    def activate(self):
        self.compose(
            "up",
            "-d",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "180",
            timeout=210,
        )
        self.installation.check_health()

    def verify_snapshot_rows(self, database, metadata):
        with private_restore_directory(self.root, None) as scratch:

            def export(sql, selected):
                with selected.open("xb") as output:
                    self.compose(
                        "exec",
                        "-T",
                        "postgres",
                        "psql",
                        "-X",
                        "-U",
                        "kyrion",
                        "-d",
                        database,
                        "-v",
                        "ON_ERROR_STOP=1",
                        "-Atc",
                        sql,
                        output=output,
                    )

            _, records = capture_rows(
                lambda sql: self.query(sql, database=database), export, scratch / "rows"
            )
            expected = {
                name: row["sha256"]
                for name, row in self.backup_manifest["files"].items()
                if name.startswith("database-data/")
            }
            if {
                name: sha256(selected) for name, selected in records.items()
            } != expected:
                raise ValueError("E_UPDATE_SNAPSHOT_CHANGED")
