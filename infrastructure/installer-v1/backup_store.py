"""Protected operational backup storage; never adopt or prune unknown files."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import uuid
from pathlib import Path

from bundle import sha256
from host import reject_links
from restore_material import private_output

MARKER = ".kyrion-backup-store.json"
KEY = ".maintenance-secrets/backup.key"


def normalize(destination: Path, target: Path) -> Path:
    if not destination.is_absolute():
        raise ValueError("E_BACKUP_STORE")
    reject_links(destination)
    destination = destination.resolve()
    if (
        destination == destination.parent
        or destination.is_relative_to(target.resolve())
        or target.resolve().is_relative_to(destination)
    ):
        raise ValueError("E_BACKUP_STORE")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes as w

        if destination.drive.startswith("\\") or len(str(destination)) > 180:
            raise ValueError("E_BACKUP_STORE")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetDriveTypeW.argtypes = [w.LPCWSTR]
        kernel.GetDriveTypeW.restype = w.UINT
        if kernel.GetDriveTypeW(destination.anchor) not in {2, 3}:
            raise ValueError("E_BACKUP_STORE")
    return destination


def publish(path: Path, raw: bytes, security_source: Path) -> None:
    """Publish complete private bytes exclusively; leave prior files untouched."""
    reject_links(path)
    temporary = path.with_name("." + path.name + ".pending-" + uuid.uuid4().hex)
    try:
        with private_output(temporary, security_source) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
        reject_links(path)
        if sha256(path) != hashlib.sha256(raw).hexdigest():
            raise ValueError("E_BACKUP_PUBLICATION")
        if os.name == "posix":
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except OSError as error:
        raise ValueError("E_BACKUP_PUBLICATION") from error
    finally:
        temporary.unlink(missing_ok=True)


def validate_binding(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"path", "id", "markerSha256"}
        or not isinstance(value.get("path"), str)
        or not Path(value["path"]).is_absolute()
        or any(ord(char) < 32 for char in value["path"])
        or not isinstance(value.get("markerSha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", value["markerSha256"])
    ):
        raise ValueError("E_BACKUP_STORE")
    try:
        if str(uuid.UUID(value["id"])) != value["id"]:
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("E_BACKUP_STORE") from None


def secure_directory(path: Path, *, private: bool = True) -> None:
    reject_links(path)
    if os.name == "nt":
        from native_runtime import permissions

        permissions(path, "root-only")
        return
    for item in (path, *path.parents):
        if not item.is_dir() or item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
            raise ValueError("E_BACKUP_STORE_OWNERSHIP")
    if private and path.stat().st_mode & 0o077:
        raise ValueError("E_BACKUP_STORE_OWNERSHIP")


def create_directory(path: Path) -> None:
    reject_links(path)
    if os.name == "nt":
        from native_runtime import permissions

        permissions(path, "create")
    else:
        secure_directory(path.parent, private=False)
        path.mkdir(mode=0o700)
    secure_directory(path)


def marker_bytes(installation, identifier: str) -> bytes:
    return json.dumps(
        {
            "formatVersion": 1,
            "kind": "kyrion-backup-store",
            "installationId": str(uuid.UUID(installation.state["installationId"])),
            "id": str(uuid.UUID(identifier)),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def bindings(installation) -> list[dict]:
    values = installation.state.get("backupStores", [])
    if not isinstance(values, list) or len(values) > 32:
        raise ValueError("E_BACKUP_STORE")
    for value in values:
        validate_binding(value)
    if len({value["id"] for value in values}) != len(values) or len(
        {value["path"] for value in values}
    ) != len(values):
        raise ValueError("E_BACKUP_STORE")
    return values


def prepare(installation, destination: Path) -> dict:
    destination = normalize(destination, installation.target)
    known = bindings(installation)
    if len(known) >= 32 and not any(
        value["path"] == str(destination) for value in known
    ):
        raise ValueError("E_BACKUP_STORE")
    previous = installation.state.get("backupStoreIntent")
    if previous is not None:
        validate_binding(previous)
    if previous is None or previous["path"] != str(destination):
        previous = next(
            (value for value in known if value["path"] == str(destination)), None
        )
        if previous is None:
            policy = installation.state.get("backupPolicy")
            previous = policy.get("store") if isinstance(policy, dict) else None
        if previous is not None:
            validate_binding(previous)
        if previous is None or previous["path"] != str(destination):
            identifier = str(uuid.uuid4())
            previous = {
                "path": str(destination),
                "id": identifier,
                "markerSha256": hashlib.sha256(
                    marker_bytes(installation, identifier)
                ).hexdigest(),
            }
        installation.state["backupStoreIntent"] = previous
        installation.save()
    raw = marker_bytes(installation, previous["id"])
    if hashlib.sha256(raw).hexdigest() != previous["markerSha256"]:
        raise ValueError("E_BACKUP_STORE")
    if not destination.exists():
        create_directory(destination)
    secure_directory(destination)
    marker = destination / MARKER
    reject_links(marker)
    if marker.exists():
        if (
            not marker.is_file()
            or marker.stat().st_size != len(raw)
            or sha256(marker) != previous["markerSha256"]
        ):
            raise ValueError("E_BACKUP_STORE_OWNER")
    else:
        policy = installation.state.get("backupPolicy")
        if previous in known or (
            isinstance(policy, dict) and policy.get("store") == previous
        ):
            raise ValueError("E_BACKUP_STORE_OWNER")
        if installation.state.get("backupStorePrepared") != previous:
            if any(destination.iterdir()):
                raise ValueError("E_BACKUP_STORE_NOT_EMPTY")
            installation.state["backupStorePrepared"] = dict(previous)
            installation.save()
        publish(marker, raw, destination)
    verify(installation, previous)
    recorded = next(
        (
            value
            for value in known
            if value["path"] == str(destination) or value["id"] == previous["id"]
        ),
        None,
    )
    if recorded is not None and recorded != previous:
        raise ValueError("E_BACKUP_STORE")
    if recorded is None:
        if len(known) >= 32:
            raise ValueError("E_BACKUP_STORE")
        installation.state["backupStores"] = [*known, dict(previous)]
        installation.save()
    return dict(previous)


def verify(installation, binding: dict) -> Path:
    validate_binding(binding)
    root = Path(binding["path"])
    secure_directory(root)
    marker = root / MARKER
    reject_links(marker)
    if (
        not marker.is_file()
        or marker.stat().st_size > 4096
        or sha256(marker) != binding["markerSha256"]
        or marker.read_bytes() != marker_bytes(installation, binding["id"])
    ):
        raise ValueError("E_BACKUP_STORE_OWNER")
    return root


def read_key(installation, digest: str) -> str:
    directory = installation.target / ".maintenance-secrets"
    selected = installation.target / KEY
    reject_links(selected)
    if os.name == "nt":
        from native_runtime import permissions

        permissions(installation.target, "verify")
    elif (
        directory.stat().st_uid != 0
        or directory.stat().st_mode & 0o777 != 0o700
        or selected.stat().st_uid != 0
        or selected.stat().st_mode & 0o777 != 0o600
    ):
        raise ValueError("E_BACKUP_SCHEDULE_KEY")
    if selected.stat().st_size != 65 or sha256(selected) != digest:
        raise ValueError("E_BACKUP_SCHEDULE_KEY")
    raw = selected.read_bytes()
    if not re.fullmatch(rb"[a-f0-9]{64}\n", raw):
        raise ValueError("E_BACKUP_SCHEDULE_KEY")
    return raw.decode().strip()


def export_path(installation, export: Path, extra_store: Path | None = None) -> Path:
    if not export.is_absolute():
        raise ValueError("E_BACKUP_KEY_EXPORT")
    reject_links(export)
    export = export.resolve()
    values = list(bindings(installation))
    intent = installation.state.get("backupStoreIntent")
    if intent is not None:
        validate_binding(intent)
        values.append(intent)
    destinations = [Path(value["path"]) for value in values]
    if extra_store is not None:
        destinations.append(extra_store)
    if export.is_relative_to(installation.target.resolve()) or any(
        export.is_relative_to(path) for path in destinations
    ):
        raise ValueError("E_BACKUP_KEY_EXPORT")
    return export


def prepare_key(installation, export: Path, store: Path) -> str:
    export = export_path(installation, export, store)
    if os.name == "posix":
        secure_directory(export.parent)
    directory = installation.target / ".maintenance-secrets"
    reject_links(directory)
    if not directory.exists():
        if os.name == "nt":
            from windows_security import create_private_directory

            create_private_directory(directory)
        else:
            directory.mkdir(mode=0o700)
    selected = installation.target / KEY
    reject_links(selected)
    if not selected.exists():
        publish(selected, (secrets.token_hex(32) + "\n").encode(), directory)
    digest = sha256(selected)
    require_known_key(installation, digest)
    raw = (read_key(installation, digest) + "\n").encode()
    if export.exists():
        if (
            not export.is_file()
            or export.stat().st_size != 65
            or sha256(export) != digest
        ):
            raise ValueError("E_BACKUP_KEY_EXPORT")
    else:
        publish(export, raw, directory)
    return digest


def require_known_key(installation, digest: str) -> None:
    for field in ("automaticUpdatePolicy", "backupPolicy"):
        previous = installation.state.get(field)
        if previous is not None and (
            not isinstance(previous, dict) or previous.get("keySha256") != digest
        ):
            raise ValueError("E_BACKUP_SCHEDULE_KEY")


def validate_receipt(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"runId", "storeId", "name", "sha256", "bytes", "verifiedAt"}
        or type(value.get("bytes")) is not int
        or value["bytes"] <= 0
        or type(value.get("verifiedAt")) is not int
        or value["verifiedAt"] < 0
        or not isinstance(value.get("sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", value["sha256"])
    ):
        raise ValueError("E_BACKUP_HISTORY")
    try:
        identifier = str(uuid.UUID(value["runId"]))
        if str(uuid.UUID(value["storeId"])) != value["storeId"]:
            raise ValueError()
        if (
            identifier != value["runId"]
            or value.get("name") != "kyrion-" + uuid.UUID(identifier).hex + ".gpg"
        ):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("E_BACKUP_HISTORY") from None


def prune(installation, binding: dict, keep: int) -> None:
    if type(keep) is not int or not 1 <= keep <= 90:
        raise ValueError("E_BACKUP_POLICY")
    root = verify(installation, binding)
    history = installation.state.get("backupHistory", [])
    if not isinstance(history, list) or len(history) > 1000:
        raise ValueError("E_BACKUP_HISTORY")
    for receipt in history:
        validate_receipt(receipt)
    if len({item["runId"] for item in history}) != len(history):
        raise ValueError("E_BACKUP_HISTORY")
    owned = [item for item in history if item["storeId"] == binding["id"]]
    while len(owned) > keep:
        receipt = owned[0]
        selected = root / receipt["name"]
        reject_links(selected)
        if selected.exists():
            if (
                not selected.is_file()
                or selected.stat().st_size != receipt["bytes"]
                or sha256(selected) != receipt["sha256"]
            ):
                raise ValueError("E_BACKUP_RETENTION_CHANGED")
            selected.unlink()
        owned.pop(0)
        history.remove(receipt)
        installation.state["backupHistory"] = history
        installation.save()
