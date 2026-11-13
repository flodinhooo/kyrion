"""Restore only data and original application keys, never archived host code."""

from __future__ import annotations

import hashlib
import os
import tarfile
import uuid
from pathlib import Path

from bundle import sha256
from host import reject_links


def read_member(archive: Path, name: str, maximum: int) -> bytes:
    with tarfile.open(archive) as package:
        item = package.getmember(name)
        if not item.isfile() or item.size > maximum:
            raise ValueError("E_RESTORE_MATERIAL")
        with package.extractfile(item) as stream:
            return stream.read(maximum + 1)


def extract_rows(archive: Path, manifest: dict, scratch: Path) -> dict[str, Path]:
    files = {}
    with tarfile.open(archive) as package:
        for name in manifest["files"]:
            if not name.startswith("database-data/"):
                continue
            path = scratch / ("row-" + uuid.uuid4().hex)
            with (
                package.extractfile(name) as source,
                private_output(path, scratch) as destination,
            ):
                import shutil

                shutil.copyfileobj(source, destination, 1024**2)
            if sha256(path) != manifest["files"][name]["sha256"]:
                raise ValueError("E_BACKUP_INTEGRITY")
            files[name] = path
    return files


def private_output(path: Path, security_source: Path):
    if os.name == "nt":
        from windows_security import open_secured_file

        return os.fdopen(open_secured_file(path, security_source), "wb")
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def data_owner(installation, name: str, path: Path) -> None:
    """Host recovery tooling runs as the same Linux UID as Core, not root."""
    if os.name != "posix":
        return
    if name.startswith("data/knowledge/"):
        os.chown(path, 10001, 10001)
    elif name.startswith("recovery/") and name.endswith(".host-key"):
        filename = name.removeprefix("recovery/")
        try:
            identifier = str(uuid.UUID(filename.removesuffix(".host-key")))
        except ValueError:
            raise ValueError("E_RESTORE_MATERIAL") from None
        if filename != identifier + ".host-key":
            raise ValueError("E_RESTORE_MATERIAL")
        directory = installation.target / "recovery"
        reject_links(directory)
        reject_links(path)
        os.chown(directory, 10001, 10001)
        os.chown(path, 10001, 10001)


def reconcile_managed(installation) -> None:
    for name, operation in installation.state.get("restoreFileOperations", {}).items():
        if (
            name
            not in {
                "secrets/credential.key",
                "secrets/audit-integrity.key",
                "identity-provider.json",
                ".env",
            }
            or not isinstance(operation, dict)
            or set(operation) != {"old", "new"}
        ):
            raise ValueError("E_RESTORE_REQUEST_CONFLICT")
        path = installation.target / name
        reject_links(path)
        actual = sha256(path) if path.is_file() else None
        if actual not in {operation["old"], operation["new"]}:
            raise ValueError("E_RESTORE_TARGET_CHANGED")
        if actual == operation["new"]:
            installation.state["files"][name] = actual
    installation.save()
    installation.verify_files()


def replace_managed(installation, name: str, raw: bytes) -> None:
    """Two known file digests permit recovery after atomic replace + lost save."""
    path = installation.target / name
    reject_links(path)
    expected = hashlib.sha256(raw).hexdigest()
    operations = installation.state.setdefault("restoreFileOperations", {})
    operation = operations.get(name)
    if operation is None:
        old = installation.state["files"].get(name)
        if path.exists() and (old is None or sha256(path) != old):
            raise ValueError("E_RESTORE_TARGET_CHANGED")
        operation = {"old": old, "new": expected}
        operations[name] = operation
        installation.save()
    elif operation.get("new") != expected:
        raise ValueError("E_RESTORE_REQUEST_CONFLICT")
    if path.exists() and sha256(path) not in {operation["old"], expected}:
        raise ValueError("E_RESTORE_TARGET_CHANGED")
    if not path.exists() or sha256(path) != expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        reject_links(path.parent)
        temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
        source = path if path.exists() else installation.path
        try:
            with private_output(temporary, source) as stream:
                if os.name == "posix" and path.exists():
                    original = path.stat()
                    os.fchmod(stream.fileno(), original.st_mode & 0o777)
                    os.fchown(stream.fileno(), original.st_uid, original.st_gid)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    installation.state["files"][name] = expected
    installation.save()


def restore_keys_and_data(installation, archive: Path, manifest: dict) -> None:
    for name in ("secrets/credential.key", "secrets/audit-integrity.key"):
        key = read_member(archive, name, 32)
        if len(key) != 32:
            raise ValueError("E_RESTORE_MATERIAL")
        replace_managed(installation, name, key)
    recovery = installation.target / "recovery"
    if any(name.startswith("recovery/") for name in manifest["files"]):
        reject_links(recovery)
        if not recovery.exists():
            if os.name == "nt":
                from windows_security import create_private_directory

                create_private_directory(recovery)
            else:
                recovery.mkdir(mode=0o700)
    pending = installation.state.get("restoreDataPending")
    if pending is not None:
        if (
            not isinstance(pending, dict)
            or set(pending) != {"name", "temporary", "sha256"}
            or pending["name"] not in manifest["files"]
            or not pending["name"].startswith(("data/knowledge/", "recovery/"))
        ):
            raise ValueError("E_RESTORE_REQUEST_CONFLICT")
        path = installation.target / pending["name"]
        temporary = path.with_name(pending["temporary"])
        reject_links(path)
        reject_links(temporary)
        if (
            not temporary.name.startswith("." + path.name + ".")
            or temporary.parent != path.parent
            or pending["sha256"] != manifest["files"][pending["name"]]["sha256"]
        ):
            raise ValueError("E_RESTORE_REQUEST_CONFLICT")
        if temporary.exists():
            if not path.exists() and sha256(temporary) == pending["sha256"]:
                data_owner(installation, pending["name"], temporary)
                os.replace(temporary, path)
            else:
                # Only the exact journalled temporary path is removed. Never
                # adopt or remove an unknown final document.
                temporary.unlink()
        installation.state.pop("restoreDataPending")
        installation.save()
    with tarfile.open(archive) as package:
        for name, record in manifest["files"].items():
            if not name.startswith(("data/knowledge/", "recovery/")):
                continue
            # Streaming avoids holding large personal documents in memory.
            path = installation.target / name
            reject_links(path)
            if path.exists():
                if sha256(path) != record["sha256"]:
                    raise ValueError("E_RESTORE_TARGET_CHANGED")
                data_owner(installation, name, path)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            reject_links(path.parent)
            temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
            installation.state["restoreDataPending"] = {
                "name": name,
                "temporary": temporary.name,
                "sha256": record["sha256"],
            }
            installation.save()
            try:
                policy = (
                    installation.target / "data/knowledge"
                    if name.startswith("data/knowledge/")
                    else recovery
                )
                with (
                    package.extractfile(name) as source,
                    private_output(temporary, policy) as output,
                ):
                    import shutil

                    shutil.copyfileobj(source, output, 1024**2)
                    output.flush()
                    os.fsync(output.fileno())
                if sha256(temporary) != record["sha256"]:
                    raise ValueError("E_BACKUP_INTEGRITY")
                data_owner(installation, name, temporary)
                os.replace(temporary, path)
                installation.state.pop("restoreDataPending")
                installation.save()
            finally:
                temporary.unlink(missing_ok=True)
