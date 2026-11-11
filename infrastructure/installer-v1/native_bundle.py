"""Authenticated native runtime payloads; no archive member is executable authority."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import struct
import zipfile
from pathlib import Path, PurePosixPath

from bundle import VERSION, ReviewedBundle, sha256, unique_object, verify_signature
from host import reject_links
from models import https_source
from runtime import atomic_json, installation_lock

MAXIMUM_MANIFEST = 8 * 1024**2
MAXIMUM_EXPANDED = 12 * 1024**3
COMPONENTS = frozenset({"core", "web", "java", "node", "postgres", "caddy"})
REQUIRED_FILES = frozenset(
    {
        "app/core/core-runtime.jar",
        "app/core/knowledge-parser.jar",
        "app/web/server.js",
        "runtime/java/bin/java.exe",
        "runtime/node/node.exe",
        "runtime/caddy/caddy.exe",
        *(
            "runtime/postgres/bin/" + executable + ".exe"
            for executable in (
                "postgres",
                "initdb",
                "pg_ctl",
                "pg_isready",
                "psql",
                "pg_dump",
                "pg_restore",
            )
        ),
        *("licenses/" + component + ".txt" for component in COMPONENTS),
    }
)
PREFIXES = (
    "app/core/",
    "app/web/",
    "runtime/java/",
    "runtime/node/",
    "runtime/postgres/",
    "runtime/caddy/",
    "licenses/",
)
PRIVATE_PARTS = frozenset(
    {
        ".git",
        ".ssh",
        ".aws",
        ".codex",
        ".env",
        ".npmrc",
        ".netrc",
        ".pypirc",
        ".git-credentials",
        "install-state.json",
        "id_rsa",
        "id_ed25519",
    }
)


def safe_member(name: object) -> str:
    if (
        not isinstance(name, str)
        or not 1 <= len(name) <= 230
        or "\\" in name
        or not name.startswith(PREFIXES)
    ):
        raise ValueError("E_NATIVE_PATH")
    parts = name.split("/")
    if (
        any(
            not part
            or part in {".", ".."}
            or part.endswith((".", " "))
            or any(ord(character) < 32 or character in ':<>"|?*' for character in part)
            for part in parts
        )
        or PurePosixPath(name).as_posix() != name
    ):
        raise ValueError("E_NATIVE_PATH")
    for part in parts:
        normalized = part.casefold()
        if (
            normalized in PRIVATE_PARTS
            or normalized.startswith(".env")
            or re.fullmatch(
                r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", normalized
            )
        ):
            raise ValueError("E_NATIVE_PRIVATE_OR_RESERVED_PATH")
    return name


def pe_amd64(stream) -> bool:
    header = stream.read(64)
    if len(header) != 64 or header[:2] != b"MZ":
        return False
    offset = struct.unpack_from("<I", header, 60)[0]
    if not 64 <= offset <= 1024**2:
        return False
    stream.seek(offset)
    return stream.read(6) == b"PE\0\0\x64\x86"


def validate(root: Path, authenticated_bytes: bytes | None = None) -> dict:
    reject_links(root)
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or manifest_path.stat().st_size > MAXIMUM_MANIFEST:
        raise ValueError("E_NATIVE_MANIFEST")
    raw = (
        manifest_path.read_bytes()
        if authenticated_bytes is None
        else authenticated_bytes
    )
    if len(raw) > MAXIMUM_MANIFEST:
        raise ValueError("E_NATIVE_MANIFEST")
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    fields = {
        "schemaVersion",
        "runtime",
        "release",
        "architecture",
        "components",
        "compatibility",
        "artifact",
        "files",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != fields
        or type(manifest["schemaVersion"]) is not int
        or manifest["schemaVersion"] != 2
        or manifest["runtime"] != "windows-native"
        or manifest["architecture"] != "windows/amd64"
        or not isinstance(manifest["release"], str)
        or not VERSION.fullmatch(manifest["release"])
        or "latest" in manifest["release"].lower()
    ):
        raise ValueError("E_NATIVE_MANIFEST")
    components = manifest["components"]
    if not isinstance(components, dict) or set(components) != COMPONENTS:
        raise ValueError("E_NATIVE_COMPONENTS")
    for name, component in components.items():
        if (
            not isinstance(component, dict)
            or set(component) != {"version", "sourceUrl", "license", "licenseUrl"}
            or not isinstance(component["version"], str)
            or not re.fullmatch(r"[0-9][A-Za-z0-9._+-]{0,79}", component["version"])
            or "latest" in component["version"].lower()
            or not isinstance(component["license"], str)
            or not 1 <= len(component["license"]) <= 200
            or any(ord(character) < 32 for character in component["license"])
            or not https_source(component["sourceUrl"])
            or not (
                https_source(component["licenseUrl"])
                or (
                    name in {"core", "web"}
                    and component["licenseUrl"] is None
                    and component["license"].startswith("LicenseRef-")
                )
            )
            or name in {"core", "web"}
            and component["version"] != manifest["release"]
        ):
            raise ValueError("E_NATIVE_COMPONENT")
    compatibility = manifest["compatibility"]
    if (
        not isinstance(compatibility, dict)
        or set(compatibility) != {"api", "schema", "postgresMajor"}
        or any(
            type(compatibility[key]) is not int or compatibility[key] < 1
            for key in compatibility
        )
        or compatibility["postgresMajor"] != 17
        or not components["postgres"]["version"].startswith("17.")
        or not components["java"]["version"].startswith("21.")
        or not components["node"]["version"].startswith("22.")
    ):
        raise ValueError("E_NATIVE_COMPATIBILITY")
    artifact = manifest["artifact"]
    if (
        not isinstance(artifact, dict)
        or set(artifact) != {"name", "sha256", "bytes"}
        or artifact["name"] != "kyrion-windows-amd64.zip"
        or type(artifact["bytes"]) is not int
        or not 0 < artifact["bytes"] <= MAXIMUM_EXPANDED
        or not isinstance(artifact["sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"])
    ):
        raise ValueError("E_NATIVE_ARTIFACT")
    archive_path = root / artifact["name"]
    if (
        archive_path.is_symlink()
        or not archive_path.is_file()
        or archive_path.stat().st_size != artifact["bytes"]
        or sha256(archive_path) != artifact["sha256"]
    ):
        raise ValueError("E_NATIVE_DIGEST")
    rows = manifest["files"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20000:
        raise ValueError("E_NATIVE_FILES")
    files = {}
    aliases = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
            raise ValueError("E_NATIVE_FILES")
        path = safe_member(row["path"])
        if (
            path.casefold() in aliases
            or type(row["bytes"]) is not int
            or not 0 <= row["bytes"] <= 1024**3
            or not isinstance(row["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"])
        ):
            raise ValueError("E_NATIVE_FILES")
        aliases.add(path.casefold())
        files[path] = row
    if (
        not REQUIRED_FILES <= files.keys()
        or any(files[name]["bytes"] <= 0 for name in REQUIRED_FILES)
        or sum(row["bytes"] for row in files.values()) > MAXIMUM_EXPANDED
    ):
        raise ValueError("E_NATIVE_REQUIRED_FILES")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) != len(files) or len(
            {member.filename for member in members}
        ) != len(members):
            raise ValueError("E_NATIVE_ARCHIVE_ENTRIES")
        for member in members:
            path = safe_member(member.filename)
            mode = member.external_attr >> 16
            if (
                path not in files
                or member.is_dir()
                or stat.S_ISLNK(mode)
                or stat.S_IFMT(mode) not in {0, stat.S_IFREG}
                or member.flag_bits & 1
                or member.compress_type
                not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                or member.file_size != files[path]["bytes"]
            ):
                raise ValueError("E_NATIVE_ARCHIVE_ENTRY")
            with archive.open(member) as stream:
                if (
                    hashlib.file_digest(stream, "sha256").hexdigest()
                    != files[path]["sha256"]
                ):
                    raise ValueError("E_NATIVE_FILE_DIGEST")
            if path.lower().endswith((".exe", ".dll", ".node")):
                with archive.open(member) as stream:
                    if not pe_amd64(stream):
                        raise ValueError("E_NATIVE_BINARY_ARCHITECTURE")
    return manifest


def authenticated_review(root: Path, public_key: Path) -> ReviewedBundle:
    raw = verify_signature(root, public_key, MAXIMUM_MANIFEST)
    return ReviewedBundle(validate(root, raw), hashlib.sha256(raw).hexdigest())


def authenticate(root: Path, public_key: Path) -> dict:
    return authenticated_review(root, public_key).manifest


def copy_member(
    archive: zipfile.ZipFile, name: str, temporary: Path, expected: dict
) -> None:
    digest = hashlib.sha256()
    count = 0
    with archive.open(name) as source, temporary.open("xb") as output:
        while chunk := source.read(1024**2):
            count += len(chunk)
            if count > expected["bytes"]:
                raise ValueError("E_NATIVE_FILE_SIZE")
            digest.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    if count != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
        raise ValueError("E_NATIVE_FILE_DIGEST")


def unpack(root: Path, public_key: Path, destination: Path) -> dict:
    """Resume immutable public payload extraction, never overwrite active data.

    The caller owns/protects the parent. Native Windows ACL preparation and
    runtime activation remain separate operations.
    """
    reviewed = authenticated_review(root, public_key)
    if (
        not destination.is_absolute()
        or destination == destination.parent
        or not destination.parent.is_dir()
    ):
        raise ValueError("E_NATIVE_DESTINATION")
    reject_links(destination)
    with installation_lock(destination):
        return _unpack_reviewed(root, reviewed, destination)


def _unpack_reviewed(root: Path, reviewed: ReviewedBundle, destination: Path) -> dict:
    manifest = reviewed.manifest
    manifest_digest = reviewed.manifest_sha256
    files = {row["path"]: row for row in manifest["files"]}
    receipt_path = destination / ".kyrion-native-payload.json"
    if destination.exists():
        if (
            not receipt_path.is_file()
            or receipt_path.is_symlink()
            or receipt_path.stat().st_size > MAXIMUM_MANIFEST
        ):
            raise ValueError("E_NATIVE_EXISTING")
        state = json.loads(
            receipt_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
        )
        # Validate legacy receipts before migrating their informational progress.
        if isinstance(state, dict) and state.get("formatVersion") == 1:
            completed = state.get("completed")
            if (
                not isinstance(completed, list)
                or not all(
                    isinstance(name, str) and name in files for name in completed
                )
                or len(completed) != len(set(completed))
            ):
                raise ValueError("E_NATIVE_STATE")
            state["completed"] = len(completed)
            state["formatVersion"] = 2
        if (
            not isinstance(state, dict)
            or set(state)
            != {
                "formatVersion",
                "rootPath",
                "manifestSha256",
                "completed",
                "preserved",
                "pending",
                "complete",
            }
            or type(state["formatVersion"]) is not int
            or state["formatVersion"] != 2
            or type(state["complete"]) is not bool
            or state["rootPath"] != str(destination.resolve())
            or state["manifestSha256"] != manifest_digest
            or type(state["completed"]) is not int
            or not 0 <= state["completed"] <= len(files)
            or not isinstance(state["preserved"], list)
            or len(state["preserved"]) > 128
            or not all(
                isinstance(name, str)
                and re.fullmatch(r"\.native-part-[a-f0-9]{32}", name)
                for name in state["preserved"]
            )
            or len(state["preserved"]) != len(set(state["preserved"]))
        ):
            raise ValueError("E_NATIVE_STATE")
    else:
        destination.mkdir(mode=0o700)
        state = {
            "formatVersion": 2,
            "rootPath": str(destination.resolve()),
            "manifestSha256": manifest_digest,
            "completed": 0,
            "preserved": [],
            "pending": None,
            "complete": False,
        }
        atomic_json(receipt_path, state)
    pending = state["pending"]
    if pending is not None and (
        not isinstance(pending, dict)
        or set(pending) != {"path", "temporary"}
        or not isinstance(pending["path"], str)
        or pending["path"] not in files
        or not isinstance(pending["temporary"], str)
        or not re.fullmatch(r"\.native-part-[a-f0-9]{32}", pending["temporary"])
    ):
        raise ValueError("E_NATIVE_STATE")
    allowed_directories = {
        parent.as_posix()
        for name in files
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }
    allowed_temporaries = set(state["preserved"]) | (
        {pending["temporary"]} if pending else set()
    )
    allowed_files = set(files) | allowed_temporaries | {receipt_path.name}
    orphan_receipts = 0
    for item in destination.rglob("*"):
        reject_links(item)
        relative = item.relative_to(destination).as_posix()
        # A killed process can leave its exclusive atomic-journal temporary.
        # Preserve it without interpreting it or accepting it as runtime content.
        if re.fullmatch(r"\.\.kyrion-native-payload\.json\.[a-f0-9]{16}", relative):
            orphan_receipts += 1
            if (
                not item.is_file()
                or item.stat().st_size > MAXIMUM_MANIFEST
                or orphan_receipts > 128
            ):
                raise ValueError("E_NATIVE_PARTIAL_REVIEW")
            continue
        if item.is_dir() and relative in allowed_directories:
            continue
        if not item.is_file() or relative not in allowed_files:
            raise ValueError("E_NATIVE_EXISTING")
    # Incomplete public runtime bytes remain outside the application tree and
    # are preserved, never adopted as secret material or silently deleted.
    if pending and (destination / pending["temporary"]).exists():
        if len(state["preserved"]) >= 128:
            raise ValueError("E_NATIVE_PARTIAL_REVIEW")
        state["preserved"].append(pending["temporary"])
    state["pending"] = None
    state["completed"] = 0
    state["complete"] = False
    atomic_json(receipt_path, state)
    with zipfile.ZipFile(root / manifest["artifact"]["name"]) as archive:
        for name, expected in sorted(files.items()):
            path = destination / name
            reject_links(path)
            if path.exists():
                if (
                    not path.is_file()
                    or path.stat().st_size != expected["bytes"]
                    or sha256(path) != expected["sha256"]
                ):
                    raise ValueError("E_NATIVE_CHANGED")
            else:
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                temporary_name = ".native-part-" + secrets.token_hex(16)
                temporary = destination / temporary_name
                state["pending"] = {"path": name, "temporary": temporary_name}
                atomic_json(receipt_path, state)
                copy_member(archive, name, temporary, expected)
                # Hard-link creation is atomic and refuses an existing target.
                # No archive member is ever allowed to be a link itself.
                os.link(temporary, path)
                temporary.unlink()
            state["completed"] += 1
            state["pending"] = None
            atomic_json(receipt_path, state)
    state["complete"] = True
    atomic_json(receipt_path, state)
    return {
        "release": manifest["release"],
        "payloadVerified": True,
        "files": len(files),
        "preservedPartials": len(state["preserved"]),
        "runtimeActivated": False,
    }
