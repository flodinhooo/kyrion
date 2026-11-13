"""Bounded update journal and old/new configuration reconciliation."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import uuid
from pathlib import Path

from bundle import sha256
from host import reject_links
from restore_material import private_output

PHASES = frozenset(
    {
        "preparing",
        "backing-up",
        "snapshotting",
        "switching",
        "migrating",
        "checking",
        "activating",
        "complete",
        "recovery-preparing",
        "recovering-runtime",
        "recovering-db",
        "recovery-checking",
        "reactivating",
        "recovered",
    }
)


def transaction(installation) -> dict:
    value = installation.state.get("updateTransaction")
    if (
        not isinstance(value, dict)
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
    ):
        raise ValueError("E_UPDATE_TRANSACTION")
    try:
        identifier = str(uuid.UUID(value["id"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ValueError("E_UPDATE_TRANSACTION") from None
    if (
        identifier != value["id"]
        or value.get("phase") not in PHASES
        or value.get("directory") != "transaction/" + uuid.UUID(identifier).hex[:16]
    ):
        raise ValueError("E_UPDATE_TRANSACTION")
    for name in ("source", "target"):
        config = value.get(name)
        if not isinstance(config, dict) or set(config) != {
            "hostname",
            "address",
            "release",
            "manifestSha256",
            "architecture",
        }:
            raise ValueError("E_UPDATE_TRANSACTION")
        if not re.fullmatch(r"[a-f0-9]{64}", config.get("manifestSha256", "")):
            raise ValueError("E_UPDATE_TRANSACTION")
    if any(
        value["source"][field] != value["target"][field]
        for field in ("hostname", "address", "architecture")
    ):
        raise ValueError("E_UPDATE_TRANSACTION")
    if not isinstance(value.get("files"), dict) or set(value["files"]) not in (
        {".env", "compose.yml"},
        {"native-manifest.json"},
    ):
        raise ValueError("E_UPDATE_TRANSACTION")
    aliases = value.get("sourceAliases", {})
    if (
        not isinstance(aliases, dict)
        or set(aliases) not in (set(), {"compose.yml"})
        or not set(aliases) <= set(value["files"])
        or any(
            not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
            for digest in aliases.values()
        )
    ):
        raise ValueError("E_UPDATE_TRANSACTION")
    return value


def path(installation, name: str) -> Path:
    if name not in {
        "backup.gpg",
        "post-activation.gpg",
        "source-config",
        "target-config",
        "source-compose",
        "original-compose",
        "target-compose",
        "maintenance.yml",
    }:
        raise ValueError("E_UPDATE_TRANSACTION")
    value = transaction(installation)
    result = installation.target / value["directory"] / name
    reject_links(result)
    return result


def reconcile(installation) -> None:
    value = transaction(installation)
    for name, versions in value["files"].items():
        if not isinstance(versions, dict) or set(versions) != {"source", "target"}:
            raise ValueError("E_UPDATE_TRANSACTION")
        actual = sha256(installation.target / name)
        matching = [kind for kind in ("source", "target") if versions[kind] == actual]
        if value.get("sourceAliases", {}).get(name) == actual:
            matching.append("source")
        if not matching:
            raise ValueError("E_UPDATE_CHANGED")
        installation.state["files"][name] = actual
        if name == "compose.yml":
            remember_images(installation, matching[0])
        if name in {".env", "native-manifest.json"}:
            kind = matching[0]
            installation.configuration = copy.deepcopy(value[kind])
            installation.state["configuration"] = installation.configuration
    installation.save()
    from update_data import reconcile_pending

    reconcile_pending(installation)
    installation.save()
    installation.verify_files()


def select_configuration(installation, kind: str) -> None:
    if kind not in {"source", "target"}:
        raise ValueError("E_UPDATE_TRANSACTION")
    value = transaction(installation)
    for name in value["files"]:
        suffix = "compose" if name == "compose.yml" else "config"
        raw = path(installation, kind + "-" + suffix).read_bytes()
        expected = value["files"][name][kind]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("E_UPDATE_CHANGED")
        current = installation.target / name
        reject_links(current)
        allowed = {
            *value["files"][name].values(),
            value.get("sourceAliases", {}).get(name),
        }
        if sha256(current) not in allowed:
            raise ValueError("E_UPDATE_CHANGED")
        temporary = current.with_name(".update-config-" + uuid.uuid4().hex[:12])
        try:
            with private_output(temporary, current) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, current)
        finally:
            temporary.unlink(missing_ok=True)
        installation.state["files"][name] = expected
        if name == "compose.yml":
            remember_images(installation, kind)
    installation.configuration = copy.deepcopy(value[kind])
    installation.state["configuration"] = installation.configuration
    installation.save()


def remember_images(installation, kind: str) -> None:
    value = transaction(installation)
    if value.get("targetImages") is None:
        return
    from docker_images import image_set

    images = (
        value["targetImages"] if kind == "target" else value["original"].get("images")
    )
    image_set(images)
    installation.state["runtimeImageIds"] = images.copy()


def phase(installation, value: str) -> None:
    if value not in PHASES:
        raise ValueError("E_UPDATE_TRANSACTION")
    transaction(installation)["phase"] = value
    installation.save()
