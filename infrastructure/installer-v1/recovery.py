"""Scoped consistent backups and isolated PostgreSQL restore verification.

Uses the repository's GnuPG recovery format boundary; no custom cryptography.
This never restores over a live installation or asserts full application recovery.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path, PurePosixPath

from bundle import sha256
from host import reject_links, runtime_checks
from runtime import Installation, atomic_json, execute, installation_lock

MAX_BACKUP = 128 * 1024**3
MAX_FILES = 100_000
COUNTS_SQL = "SELECT json_build_object('users',(SELECT count(*) FROM user_account),'spaces',(SELECT count(*) FROM kyrion_space),'audit',(SELECT count(*) FROM activity_event))"


def load_installation(target: Path, verify: bool = True) -> Installation:
    if not target.is_absolute() or target == target.parent:
        raise ValueError("E_TARGET")
    reject_links(target)
    path = target / "install-state.json"
    reject_links(path)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("E_STATE")
    if os.name == "posix" and (
        path.stat().st_mode & 0o077 or path.stat().st_uid != os.geteuid()
    ):
        raise ValueError("E_STATE")
    state = json.loads(path.read_text(encoding="utf-8"))
    config = state["configuration"]
    return Installation(
        target,
        config,
        config["manifestSha256"],
        config["hostname"],
        config["address"],
        verify=verify,
    )


def crypto(
    source: Path, destination: Path, password: str, decrypt: bool = False
) -> None:
    if len(password) < 16 or any(ch in password for ch in "\r\n\x00"):
        raise ValueError("E_RECOVERY_PASSWORD")
    reject_links(source)
    reject_links(destination)
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError("E_EXISTING_STATE")
    if not shutil.which("gpg"):
        raise ValueError("E_GPG_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="kyrion-gpg-") as directory:
        home = Path(directory)
        os.chmod(home, 0o700)
        home_argument = str(home)
        gpg_binary = Path(shutil.which("gpg"))
        # MSYS GnuPG (for example Git for Windows) needs a POSIX homedir for
        # its agent socket path. Native GnuPG keeps the normal Windows path.
        if os.name == "nt" and gpg_binary.with_name("msys-2.0.dll").is_file():
            home_argument = "/" + home.drive[0].lower() + home.as_posix()[2:]
        arguments = [
            "gpg",
            "--no-options",
            "--homedir",
            home_argument,
            "--batch",
            "--pinentry-mode",
            "loopback",
            "--no-symkey-cache",
            "--passphrase-fd",
            "0",
            "--output",
            str(destination),
        ]
        arguments += (
            ["--decrypt", str(source)]
            if decrypt
            else [
                "--cipher-algo",
                "AES256",
                "--compress-algo",
                "none",
                "--symmetric",
                str(source),
            ]
        )
        try:
            result = subprocess.run(
                arguments,
                input=(password + "\n").encode(),
                capture_output=True,
                timeout=1800,
                check=False,
            )
            if result.returncode:
                raise ValueError(
                    "E_BACKUP_INTEGRITY" if decrypt else "E_BACKUP_ENCRYPTION"
                )
            os.chmod(destination, 0o600)
            if os.name == "posix":
                with destination.open("rb") as stream:
                    os.fsync(stream.fileno())
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("E_BACKUP_CRYPTO") from error
        finally:
            if shutil.which("gpgconf"):
                subprocess.run(
                    ["gpgconf", "--homedir", home_argument, "--kill", "gpg-agent"],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
            # GPG can emit unauthenticated plaintext before reporting a bad MDC.
            # Callers keep this output only in protected scratch; no extraction
            # or promotion happens unless the command returns success.


def file_record(path: Path) -> dict:
    reject_links(path)
    if not path.is_file():
        raise ValueError("E_BACKUP_SOURCE")
    before = path.stat()
    digest = sha256(path)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError("E_BACKUP_SOURCE_CHANGED")
    return {"bytes": after.st_size, "sha256": digest, "mtimeNs": after.st_mtime_ns}


def create_archive(sources: dict[str, Path], metadata: dict, output: Path) -> dict:
    if output.exists() or len(sources) > MAX_FILES:
        raise ValueError("E_BACKUP_TARGET")
    records = {name: file_record(path) for name, path in sources.items()}
    if sum(record["bytes"] for record in records.values()) > MAX_BACKUP:
        raise ValueError("E_BACKUP_SIZE")
    manifest = {
        "formatVersion": 1,
        "kind": "kyrion-consistent-backup",
        "metadata": metadata,
        "files": records,
    }
    with tempfile.TemporaryDirectory(prefix="kyrion-manifest-") as directory:
        manifest_path = Path(directory) / "backup.json"
        atomic_json(manifest_path, manifest)
        with (
            output.open("xb") as stream,
            tarfile.open(fileobj=stream, mode="w") as archive,
        ):
            archive.add(manifest_path, arcname="backup.json", recursive=False)
            for name, path in sources.items():
                if not allowed_member(name):
                    raise ValueError("E_BACKUP_PATH")
                archive.add(path, arcname=name, recursive=False)
                if file_record(path) != records[name]:
                    raise ValueError("E_BACKUP_SOURCE_CHANGED")
    return manifest


def allowed_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not any(ord(ch) < 32 for ch in name)
        and ":" not in name
        and "\\" not in name
        and not path.is_absolute()
        and ".." not in path.parts
        and str(path) == name
        and (
            name
            in {
                "database.dump",
                "install-state.json",
                "compose.yml",
                ".env",
                "data/Caddyfile",
            }
            or name.startswith(
                ("secrets/", "data/tls/", "data/knowledge/", "recovery/")
            )
        )
    )


def inspect_archive(path: Path) -> dict:
    try:
        return _inspect_archive(path)
    except (
        OSError,
        tarfile.TarError,
        KeyError,
        TypeError,
        AttributeError,
        json.JSONDecodeError,
    ):
        raise ValueError("E_BACKUP_INVALID") from None


def _inspect_archive(path: Path) -> dict:
    with tarfile.open(path) as archive:
        names = set()
        members = []
        total = 0
        for member in archive:
            total += member.size
            if (
                len(members) >= MAX_FILES + 1
                or total > MAX_BACKUP
                or not member.isfile()
                or member.name in names
                or (member.name != "backup.json" and not allowed_member(member.name))
            ):
                raise ValueError("E_BACKUP_PATH")
            names.add(member.name)
            members.append(member)
        header = archive.getmember("backup.json")
        if header.size > 32 * 1024 * 1024:
            raise ValueError("E_BACKUP_MANIFEST")
        manifest = json.load(archive.extractfile(header))
        if (
            manifest.get("formatVersion") != 1
            or manifest.get("kind") != "kyrion-consistent-backup"
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != names - {"backup.json"}
        ):
            raise ValueError("E_BACKUP_MANIFEST")
        for member in members:
            if member.name == "backup.json":
                continue
            expected = manifest["files"][member.name]
            if expected.get("bytes") != member.size:
                raise ValueError("E_BACKUP_INTEGRITY")
            with archive.extractfile(member) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected.get(
                    "sha256"
                ):
                    raise ValueError("E_BACKUP_INTEGRITY")
        return manifest


def capture(installation: Installation, destination: Path, password: str) -> dict:
    installation.verify_files()
    if not {
        "secrets/credential.key",
        "secrets/audit-integrity.key",
        "secrets/postgres-password",
        "compose.yml",
        ".env",
    }.issubset(installation.state["files"]):
        raise ValueError("E_BACKUP_INCOMPLETE")
    reject_links(destination)
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError("E_BACKUP_TARGET")
    # Scratch is inside the root-private installation, not an unprotected volume.
    with tempfile.TemporaryDirectory(
        prefix=".backup-", dir=installation.target
    ) as directory:
        scratch = Path(directory)
        os.chmod(scratch, 0o700)
        rows = installation.compose("ps", "--format", "json").strip()
        services = (
            json.loads(rows)
            if rows.startswith("[")
            else [json.loads(row) for row in rows.splitlines() if row]
        )
        core_running = any(
            row.get("Service") == "core" and row.get("State") == "running"
            for row in services
        )
        if core_running:
            installation.compose("stop", "--timeout", "30", "core")
        try:
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
                "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'",
            ).strip()
            if not schema.isdigit():
                raise ValueError("E_BACKUP_SCHEMA")
            dump = scratch / "database.dump"
            # Do not decode a PostgreSQL custom dump or hold it all in memory.
            with dump.open("xb") as stream:
                result = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "--project-name",
                        "kyrion-" + installation.state["installationId"],
                        "--env-file",
                        str(installation.target / ".env"),
                        "-f",
                        str(installation.target / "compose.yml"),
                        "exec",
                        "-T",
                        "postgres",
                        "pg_dump",
                        "--format=custom",
                        "--no-owner",
                        "--no-acl",
                        "-U",
                        "kyrion",
                        "-d",
                        "kyrion",
                    ],
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    timeout=300,
                    check=False,
                )
            if result.returncode or dump.stat().st_size == 0:
                raise ValueError("E_BACKUP_DATABASE")
            sources = {
                relative: installation.target / relative
                for relative in installation.state["files"]
            }
            sources.update(
                {"install-state.json": installation.path, "database.dump": dump}
            )
            for relative in ("data/knowledge", "recovery"):
                tree = installation.target / relative
                if tree.exists():
                    reject_links(tree)
                    for path in tree.rglob("*"):
                        reject_links(path)
                        if path.is_file():
                            sources[
                                path.relative_to(installation.target).as_posix()
                            ] = path
            metadata = {
                "installationId": installation.state["installationId"],
                "configuration": installation.configuration,
                "schema": int(schema),
                "postgresMajor": 17,
                "restoreVerified": False,
                "coverage": [
                    "database",
                    "managed-configuration",
                    "original-keys",
                    "tls",
                    "knowledge",
                ],
                "excluded": [
                    "external-provider-state",
                    "radio-networks",
                    "foreign-ollama",
                    "central-provider-database",
                ],
            }
            counts = json.loads(
                installation.compose(
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "kyrion",
                    "-d",
                    "kyrion",
                    "-Atc",
                    COUNTS_SQL,
                )
            )
            if (
                not isinstance(counts, dict)
                or set(counts) != {"users", "spaces", "audit"}
                or any(type(value) is not int or value < 0 for value in counts.values())
            ):
                raise ValueError("E_BACKUP_COUNTS")
            metadata["verificationCounts"] = counts
            if any(name.startswith("recovery/") for name in sources):
                metadata["coverage"].append("host-recovery-material")
            archive = scratch / "backup.tar"
            create_archive(sources, metadata, archive)
            inspect_archive(archive)
        finally:
            if core_running:
                installation.compose("start", "core")
        # Keep the outage bounded to consistent capture, not encryption duration.
        temporary = destination.with_name(
            "." + destination.name + "." + uuid.uuid4().hex
        )
        try:
            crypto(archive, temporary, password)
            os.link(temporary, destination)
            if os.name == "posix":
                descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
    receipt = {
        "formatVersion": 1,
        "sha256": sha256(destination),
        "bytes": destination.stat().st_size,
        "integrityVerified": True,
        "restoreVerified": False,
        "coverage": metadata["coverage"],
    }
    installation.state["backup"] = "encrypted-consistent-capture"
    installation.save()
    return receipt


@contextlib.contextmanager
def verified_plaintext(source: Path, password: str):
    with tempfile.TemporaryDirectory(prefix="kyrion-restore-") as directory:
        scratch = Path(directory)
        os.chmod(scratch, 0o700)
        clear = scratch / "verified.tar"
        crypto(source, clear, password, decrypt=True)
        manifest = inspect_archive(clear)
        yield clear, manifest, scratch


def verify_database(source: Path, password: str, image_id: str) -> dict:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("E_IMAGE_PIN")
    with verified_plaintext(source, password) as (archive_path, manifest, scratch):
        if manifest["metadata"].get("postgresMajor") != 17:
            raise ValueError("E_BACKUP_COMPATIBILITY")
        # Never connect to a caller-provided named/live database. Always create
        # a fresh random, network-none, temporary, labelled restore target.
        name = "kyrion-restore-" + uuid.uuid4().hex
        container = execute(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "--label",
                "io.kyrion.restore-target=true",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=1073741824",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-e",
                "POSTGRES_USER=kyrion",
                "-e",
                "POSTGRES_DB=kyrion",
                image_id,
            ]
        ).strip()
        if not re.fullmatch(r"[a-f0-9]{64}", container):
            raise ValueError("E_RESTORE_CONTAINER")
        try:
            inspected = json.loads(execute(["docker", "inspect", container]))[0]
            if (
                inspected["HostConfig"]["NetworkMode"] != "none"
                or inspected["HostConfig"].get("PortBindings")
                or inspected["Config"]["Labels"].get("io.kyrion.restore-target")
                != "true"
                or any(
                    mount.get("Type") != "tmpfs"
                    for mount in inspected.get("Mounts", [])
                )
            ):
                raise ValueError("E_RESTORE_ISOLATION")
            import time

            for _ in range(30):
                ready = subprocess.run(
                    ["docker", "exec", container, "pg_isready", "-U", "kyrion"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise ValueError("E_RESTORE_DATABASE_NOT_READY")
            dump = scratch / "database.dump"
            with (
                tarfile.open(archive_path) as archive,
                archive.extractfile("database.dump") as stream,
                dump.open("xb") as output,
            ):
                shutil.copyfileobj(stream, output)
            with dump.open("rb") as stream:
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        container,
                        "pg_restore",
                        "--exit-on-error",
                        "--no-owner",
                        "--no-acl",
                        "-U",
                        "kyrion",
                        "-d",
                        "kyrion",
                    ],
                    stdin=stream,
                    capture_output=True,
                    timeout=300,
                    check=False,
                )
            if result.returncode:
                raise ValueError("E_RESTORE_DATABASE")
            schema = execute(
                [
                    "docker",
                    "exec",
                    container,
                    "psql",
                    "-U",
                    "kyrion",
                    "-d",
                    "kyrion",
                    "-Atc",
                    "SELECT max(version::integer) FROM flyway_schema_history WHERE success AND version ~ '^[0-9]+$'",
                ]
            ).strip()
            if schema != str(manifest["metadata"]["schema"]):
                raise ValueError("E_RESTORE_SCHEMA")
            expected_counts = manifest["metadata"].get("verificationCounts")
            counts_verified = False
            if expected_counts is not None:
                observed_counts = json.loads(
                    execute(
                        [
                            "docker",
                            "exec",
                            container,
                            "psql",
                            "-U",
                            "kyrion",
                            "-d",
                            "kyrion",
                            "-Atc",
                            COUNTS_SQL,
                        ]
                    )
                )
                if observed_counts != expected_counts:
                    raise ValueError("E_RESTORE_COUNTS")
                counts_verified = True
            return {
                "formatVersion": 1,
                "integrityVerified": True,
                "databaseRestoreVerified": True,
                "applicationRestoreVerified": False,
                "schema": int(schema),
                "network": "none",
                "accountSpaceAuditCountsVerified": counts_verified,
            }
        finally:
            execute(["docker", "rm", "-f", container])


def backup(target: Path, destination: Path, password: str) -> dict:
    if os.name != "posix" or os.geteuid() != 0:
        raise ValueError("E_PLATFORM")
    with installation_lock(target):
        installation = load_installation(target)
        runtime_checks(
            installation.configuration["address"],
            installation.configuration["hostname"],
            fresh=False,
        )
        return capture(installation, destination, password)
