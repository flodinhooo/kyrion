"""Recover immutable data objects, retaining changed bytes before replacement."""

from __future__ import annotations

import os
import re
import shutil
import tarfile
import uuid

from bundle import sha256
from host import reject_links
from recovery import allowed_member
from restore_material import private_output


def reconcile_pending(installation):
    value = installation.state["updateTransaction"]
    pending = value.get("pendingData")
    if pending is None:
        return
    if (
        value.get("phase") != "recovering-db"
        or not isinstance(pending, dict)
        or set(pending) != {"name", "old", "new"}
    ):
        raise ValueError("E_UPDATE_CHANGED")
    name = pending["name"]
    if (
        not isinstance(name, str)
        or not name.startswith(("data/knowledge/", "recovery/"))
        or not allowed_member(name)
        or not re.fullmatch(r"[a-f0-9]{64}", pending.get("new", ""))
        or (
            pending["old"] is not None
            and not re.fullmatch(r"[a-f0-9]{64}", pending["old"])
        )
    ):
        raise ValueError("E_UPDATE_CHANGED")
    target = installation.target / name
    reject_links(target)
    actual = sha256(target) if target.is_file() else None
    if actual not in {pending["old"], pending["new"]}:
        raise ValueError("E_UPDATE_CHANGED")
    if name in installation.state["files"] and actual is not None:
        installation.state["files"][name] = actual


def restore(installation, archive, manifest):
    value = installation.state["updateTransaction"]
    for name in ("secrets/credential.key", "secrets/audit-integrity.key"):
        if sha256(installation.target / name) != manifest["files"][name]["sha256"]:
            raise ValueError("E_UPDATE_KEY_CHANGED")
    directory = installation.target / value["directory"]
    with tarfile.open(archive) as package:
        for name, record in manifest["files"].items():
            if not name.startswith(("data/knowledge/", "recovery/")):
                continue
            target = installation.target / name
            reject_links(target)
            actual = sha256(target) if target.is_file() else None
            if value.get("pendingData") is not None:
                if value["pendingData"]["name"] != name:
                    # Earlier members are already restored; resume the single
                    # pending member before creating another checkpoint.
                    if actual == record["sha256"]:
                        continue
                    raise ValueError("E_UPDATE_CHANGED")
                reconcile_pending(installation)
            if actual == record["sha256"]:
                if value.get("pendingData", {}).get("name") == name:
                    value.pop("pendingData")
                    installation.save()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            reject_links(target.parent)
            if actual is not None:
                retained = directory / ("changed-" + actual[:24])
                reject_links(retained)
                if retained.exists():
                    if sha256(retained) != actual:
                        raise ValueError("E_UPDATE_CHANGED")
                else:
                    temporary = directory / (".retain-" + uuid.uuid4().hex[:12])
                    try:
                        with (
                            target.open("rb") as source,
                            private_output(temporary, directory) as output,
                        ):
                            shutil.copyfileobj(source, output, 1024**2)
                            output.flush()
                            os.fsync(output.fileno())
                        if sha256(temporary) != actual:
                            raise ValueError("E_UPDATE_CHANGED")
                        os.link(temporary, retained)
                    finally:
                        temporary.unlink(missing_ok=True)
            value["pendingData"] = {
                "name": name,
                "old": actual,
                "new": record["sha256"],
            }
            installation.save()
            temporary = target.with_name(".update-data-" + uuid.uuid4().hex[:12])
            policy = installation.target / (
                "data/knowledge" if name.startswith("data/knowledge/") else "recovery"
            )
            try:
                with (
                    package.extractfile(name) as source,
                    private_output(temporary, policy) as output,
                ):
                    shutil.copyfileobj(source, output, 1024**2)
                    output.flush()
                    os.fsync(output.fileno())
                if sha256(temporary) != record["sha256"]:
                    raise ValueError("E_BACKUP_INTEGRITY")
                if os.name == "posix" and name.startswith("data/knowledge/"):
                    os.chown(temporary, 10001, 10001)
                os.replace(temporary, target)
                if name in installation.state["files"]:
                    installation.state["files"][name] = record["sha256"]
                value.pop("pendingData")
                installation.save()
            finally:
                temporary.unlink(missing_ok=True)
