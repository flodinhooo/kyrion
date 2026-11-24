"""Protected restartable enrollment of the existing Linux gateway identity."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import uuid
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from kyrion_gateway_agent import __version__, client
from kyrion_gateway_agent.config import AgentConfig

IDENTITY_LIMITS = {"hostname": 253, "osName": 120, "osVersion": 80, "architecture": 40}


def private_directory(directory: Path) -> None:
    if os.name == "nt":
        from kyrion_gateway_agent.windows_storage import private_directory as windows_directory

        windows_directory(directory)
        return
    if (
        not sys.platform.startswith("linux")
        or not directory.is_absolute()
        or ".." in directory.parts
    ):
        raise ValueError("E_AGENT_PLATFORM")
    for item in (directory, *directory.parents):
        if item.is_symlink():
            raise ValueError("E_AGENT_PRIVATE_PATH")
        if item.exists():
            metadata = item.stat()
            if metadata.st_uid not in {0, os.geteuid()} or (
                metadata.st_mode & 0o022
                and not (metadata.st_uid == 0 and metadata.st_mode & stat.S_ISVTX)
            ):
                raise ValueError("E_AGENT_PRIVATE_PATH")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = directory.stat()
    if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
        raise ValueError("E_AGENT_PRIVATE_PATH")


def read_private(path: Path, maximum: int = 65536) -> bytes:
    if os.name == "nt":
        from kyrion_gateway_agent.windows_storage import read_private as windows_read

        return windows_read(path, maximum)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise ValueError("E_AGENT_PRIVATE_FILE") from error
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077
            or metadata.st_nlink != 1
        ):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("E_AGENT_PRIVATE_FILE")
    return raw


def rename_no_replace(source: Path, destination: Path) -> None:
    import ctypes
    import errno

    library = ctypes.CDLL(None, use_errno=True)
    try:
        rename = library.renameat2
    except AttributeError:
        raise ValueError("E_AGENT_PRIVATE_FILESYSTEM") from None
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError("E_AGENT_CONFIG_EXISTS")
        if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}:
            raise ValueError("E_AGENT_PRIVATE_FILESYSTEM")
        raise ValueError("E_AGENT_PRIVATE_FILE")


def publish(path: Path, raw: bytes) -> None:
    if os.name == "nt":
        from kyrion_gateway_agent.windows_storage import publish as windows_publish

        windows_publish(path, raw)
        return
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    created = False
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        rename_no_replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def enrollment_lock(path: Path):
    if os.name == "nt":
        from kyrion_gateway_agent.windows_storage import enrollment_lock as windows_lock

        with windows_lock(path):
            yield
        return
    import fcntl

    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077
            or metadata.st_nlink != 1
        ):
            raise ValueError("E_AGENT_PRIVATE_FILE")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("E_AGENT_ENROLLMENT_BUSY") from error
        yield
    finally:
        os.close(descriptor)


def read_input(path: Path, maximum: int = 128) -> bytes:
    if os.name == "nt":
        from kyrion_gateway_agent.windows_storage import read_private as windows_read

        return windows_read(path, maximum, inherited=True, current_owner=False)
    return read_private(path, maximum)


def core_url(value: str) -> str:
    value = value.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("E_AGENT_TLS_REQUIRED") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.isascii()
        or not re.fullmatch(r"[A-Za-z0-9.:-]+", parsed.hostname)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)*/?", parsed.path)
        or (port is not None and not 1 <= port <= 65535)
        or len(value) > 2048
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("E_AGENT_TLS_REQUIRED")
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("E_AGENT_ENROLLMENT_JOURNAL")
        value[key] = item
    return value


def validate_pending(value: object, path: Path) -> dict:
    fields = {
        "formatVersion",
        "core_url",
        "enrollment_token",
        "node_credential",
        "identity",
        "agent_version",
        "ca_certificate",
        "ca_sha256",
    }
    if isinstance(value, dict) and value.get("formatVersion") == 2:
        fields.add("expected_space_id")
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] not in {1, 2}
        or not isinstance(value.get("core_url"), str)
        or not isinstance(value.get("agent_version"), str)
        or not 1 <= len(value["agent_version"]) <= 40
        or not isinstance(value.get("identity"), dict)
        or set(value["identity"]) != set(IDENTITY_LIMITS)
        or any(
            not isinstance(value.get(key), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value[key])
            for key in ("enrollment_token", "node_credential")
        )
        or any(
            not isinstance(value["identity"][key], str)
            or not 1 <= len(value["identity"][key]) <= limit
            for key, limit in IDENTITY_LIMITS.items()
        )
    ):
        raise ValueError("E_AGENT_ENROLLMENT_JOURNAL")
    if value["formatVersion"] == 2:
        try:
            expected = value["expected_space_id"]
            valid = isinstance(expected, str) and str(uuid.UUID(expected)) == expected
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("E_AGENT_ENROLLMENT_JOURNAL")
    core_url(value["core_url"])
    if value["ca_certificate"] is not None:
        if value["ca_certificate"] != str(path.with_name(path.name + ".ca.pem")):
            raise ValueError("E_AGENT_ENROLLMENT_JOURNAL")
        if not isinstance(value["ca_sha256"], str) or not re.fullmatch(
            r"[a-f0-9]{64}", value["ca_sha256"]
        ):
            raise ValueError("E_AGENT_ENROLLMENT_JOURNAL")
    elif value["ca_sha256"] is not None:
        raise ValueError("E_AGENT_ENROLLMENT_JOURNAL")
    return value


def enroll_prepared(
    path: Path,
    *,
    url: str | None = None,
    token_file: Path | None = None,
    certificate: Path | None = None,
    expected_ca_sha256: str | None = None,
    identity: dict[str, str] | None = None,
    expected_space_id: str | None = None,
) -> AgentConfig:
    if expected_space_id is not None:
        try:
            valid = (
                isinstance(expected_space_id, str)
                and str(uuid.UUID(expected_space_id)) == expected_space_id
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("E_AGENT_SPACE_BINDING_INVALID")
    if expected_ca_sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", expected_ca_sha256):
        raise ValueError("E_AGENT_TLS_CONFIGURATION")
    path = path.absolute()
    private_directory(path.parent)
    pending = path.with_name(path.name + ".enrollment.json")
    with enrollment_lock(path.with_name(path.name + ".enrollment.lock")):
        if pending.is_symlink() or path.is_symlink():
            raise ValueError("E_AGENT_PRIVATE_PATH")
        if pending.exists():
            value = validate_pending(
                json.loads(read_private(pending), object_pairs_hook=unique_object), path
            )
            if (
                expected_space_id is not None
                and value.get("expected_space_id") != expected_space_id
            ):
                raise ValueError("E_AGENT_ENROLLMENT_CONFLICT")
            if expected_ca_sha256 is not None and value["ca_sha256"] != expected_ca_sha256:
                raise ValueError("E_AGENT_TLS_CONFIGURATION")
            if url is not None and core_url(url) != value["core_url"]:
                raise ValueError("E_AGENT_ENROLLMENT_CONFLICT")
            if (
                token_file is not None
                and read_input(token_file).decode("ascii").strip() != value["enrollment_token"]
            ):
                raise ValueError("E_AGENT_ENROLLMENT_CONFLICT")
            if (
                certificate is not None
                and hashlib.sha256(certificate.read_bytes()).hexdigest() != value["ca_sha256"]
            ):
                raise ValueError("E_AGENT_ENROLLMENT_CONFLICT")
        else:
            if path.exists():
                raise ValueError("E_AGENT_CONFIG_EXISTS")
            if url is None or token_file is None or identity is None:
                raise ValueError("E_AGENT_ENROLLMENT_INPUT")
            if expected_ca_sha256 is not None and certificate is None:
                raise ValueError("E_AGENT_TLS_CONFIGURATION")
            token = read_input(token_file, 128).decode("ascii").strip()
            ca_path, ca_digest = None, None
            if certificate is not None:
                with certificate.open("rb") as stream:
                    raw = stream.read(65537)
                if len(raw) > 65536 or certificate.is_symlink():
                    raise ValueError("E_AGENT_TLS_CONFIGURATION")
                selected = path.with_name(path.name + ".ca.pem")
                ca_path, ca_digest = str(selected), hashlib.sha256(raw).hexdigest()
                if expected_ca_sha256 is not None and ca_digest != expected_ca_sha256:
                    raise ValueError("E_AGENT_TLS_CONFIGURATION")
                if selected.exists():
                    if read_private(selected) != raw:
                        raise ValueError("E_AGENT_TLS_CONFIGURATION")
                else:
                    publish(selected, raw)
            value = validate_pending(
                {
                    "formatVersion": 2 if expected_space_id is not None else 1,
                    **(
                        {"expected_space_id": expected_space_id}
                        if expected_space_id is not None
                        else {}
                    ),
                    "core_url": core_url(url),
                    "enrollment_token": token,
                    "node_credential": secrets.token_urlsafe(32),
                    "identity": identity,
                    "agent_version": __version__,
                    "ca_certificate": ca_path,
                    "ca_sha256": ca_digest,
                },
                path,
            )
            # Validate trust before publishing a pending secret or sending a code.
            client.trusted_context(ca_path, ca_digest)
            publish(pending, json.dumps(value, separators=(",", ":")).encode("utf-8"))
        if path.exists():
            read_private(path)
            config = AgentConfig.load(path)
            if (
                config.core_url != value["core_url"]
                or config.gateway_token != value["node_credential"]
                or config.ca_certificate != value["ca_certificate"]
                or config.ca_sha256 != value["ca_sha256"]
                or not config.local_only
                or (
                    value.get("expected_space_id") is not None
                    and config.space_id != value["expected_space_id"]
                )
            ):
                raise ValueError("E_AGENT_ENROLLMENT_CONFLICT")
        else:
            result = client.enroll(
                value["core_url"],
                value["enrollment_token"],
                value["identity"],
                node_credential=value["node_credential"],
                ca_certificate=value["ca_certificate"],
                ca_sha256=value["ca_sha256"],
                agent_version=value["agent_version"],
                expected_space_id=value.get("expected_space_id"),
            )
            if (
                value.get("expected_space_id") is not None
                and result.space_id != value["expected_space_id"]
            ):
                raise client.CoreRequestError("E_AGENT_SPACE_BINDING_RESPONSE")
            config = AgentConfig(
                value["core_url"],
                result.node_id,
                result.gateway_token,
                value["ca_certificate"],
                value["ca_sha256"],
                True,
                result.space_id,
            )
            publish(path, json.dumps(asdict(config), separators=(",", ":")).encode("utf-8"))
        pending.unlink()
        return config


@contextlib.contextmanager
def runtime_lock(config: Path):
    config = config.absolute()
    private_directory(config.parent)
    try:
        with enrollment_lock(config.with_name(config.name + ".runtime.lock")):
            yield
    except ValueError as error:
        if str(error) == "E_AGENT_ENROLLMENT_BUSY":
            raise ValueError("E_AGENT_RUNTIME_BUSY") from None
        raise
