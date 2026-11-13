"""Explicit unattended-update consent and administrator-only backup key custody."""

from __future__ import annotations

import copy
import datetime as dt
import os
import re
import secrets
import sys
import uuid
from pathlib import Path

from authority import require_active
from bundle import sha256
from host import reject_links
from recovery import load_installation
from restore_material import private_output
from runtime import installation_lock

KEY = ".maintenance-secrets/backup.key"
EXECUTION_ATTEMPTS = 3


def reserve_attempt(installation, expected: dict) -> None:
    from update_state import transaction

    approved(installation, expected, starting=False)
    value = transaction(installation)
    if value.get("actor") != "AUTOMATIC" or value.get("automaticApproval") != expected:
        raise ValueError("E_UPDATE_AUTOMATIC_CONSENT")
    # Older compatible journals already executed at least once. Never reset
    # their budget merely because the previous worker did not record a counter.
    count = value.get("automaticAttempts", 1)
    if (
        type(count) is not int
        or not 0 <= count < EXECUTION_ATTEMPTS
        or (count == 0 and value["phase"] != "preparing")
    ):
        raise ValueError("E_UPDATE_AUTOMATIC_ATTEMPTS")
    value["automaticAttempts"] = count + 1
    value["lastAutomaticAttemptAt"] = int(dt.datetime.now(dt.timezone.utc).timestamp())
    installation.save()


def validate(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "formatVersion",
            "revision",
            "policyRevision",
            "enabled",
            "utcDays",
            "startMinute",
            "durationMinutes",
            "maximumDownloadBytes",
            "keySha256",
        }
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or type(value.get("enabled")) is not bool
        or not isinstance(value.get("utcDays"), list)
        or not 1 <= len(value["utcDays"]) <= 7
        or any(type(day) is not int or not 1 <= day <= 7 for day in value["utcDays"])
        or len(set(value["utcDays"])) != len(value["utcDays"])
        or any(
            type(value.get(key)) is not int
            for key in ("startMinute", "durationMinutes", "maximumDownloadBytes")
        )
        or not 0 <= value["startMinute"] < 1440
        or not 60 <= value["durationMinutes"] <= 720
        or not 1 <= value["maximumDownloadBytes"] <= 256 * 1024**3
        or not isinstance(value.get("keySha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", value["keySha256"])
    ):
        raise ValueError("E_UPDATE_AUTOMATIC_POLICY")
    for name in ("revision", "policyRevision"):
        try:
            if str(uuid.UUID(value[name])) != value[name]:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("E_UPDATE_AUTOMATIC_POLICY") from None


def in_window(value: dict, instant: dt.datetime | None = None) -> bool:
    validate(value)
    instant = instant or dt.datetime.now(dt.timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("E_UPDATE_AUTOMATIC_TIME")
    instant = instant.astimezone(dt.timezone.utc)
    # Yesterday's approved window can cross midnight or the week boundary.
    for offset in (0, 1):
        day = instant.date() - dt.timedelta(days=offset)
        start = dt.datetime.combine(day, dt.time(), dt.timezone.utc) + dt.timedelta(
            minutes=value["startMinute"]
        )
        if day.isoweekday() in value["utcDays"] and start <= instant < (
            start + dt.timedelta(minutes=value["durationMinutes"])
        ):
            return True
    return False


def approved(installation, expected: dict, *, starting: bool) -> dict:
    value = installation.state.get("automaticUpdatePolicy")
    validate(value)
    if (
        value != expected
        or not value["enabled"]
        or value["policyRevision"] != installation.state["updatePolicy"]["revision"]
        or not installation.state["updatePolicy"]["enabled"]
        or (starting and not in_window(value))
    ):
        raise ValueError("E_UPDATE_AUTOMATIC_CONSENT")
    return value


def password(installation, value: dict) -> str:
    validate(value)
    directory = installation.target / ".maintenance-secrets"
    selected = installation.target / KEY
    reject_links(selected)
    if os.name == "posix":
        for path, mode in ((directory, 0o700), (selected, 0o600)):
            if path.stat().st_uid != 0 or path.stat().st_mode & 0o777 != mode:
                raise ValueError("E_UPDATE_AUTOMATIC_KEY")
    else:
        from native_runtime import permissions

        permissions(installation.target, "verify")
    if selected.stat().st_size != 65 or sha256(selected) != value["keySha256"]:
        raise ValueError("E_UPDATE_AUTOMATIC_KEY")
    raw = selected.read_bytes()
    if not re.fullmatch(rb"[a-f0-9]{64}\n", raw):
        raise ValueError("E_UPDATE_AUTOMATIC_KEY")
    return raw.decode().strip()


def configure(
    target: Path,
    *,
    days: list[int],
    start: int,
    duration: int,
    maximum: int,
    export: Path,
    review,
) -> dict:
    from operational_restore import require_admin
    from update_schedule import operate
    from update_worker import require_worker, validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        policy = installation.state["updatePolicy"]
        require_worker(installation, policy)
        if not policy["enabled"]:
            raise ValueError("E_UPDATE_AUTOMATIC_CONSENT")
        # An older frozen worker cannot implement this approval protocol.
        if (
            not getattr(sys, "frozen", False)
            or sha256(Path(sys.executable))
            != installation.state["files"][policy["workerFile"]]
        ):
            raise ValueError("E_UPDATE_WORKER_CHANGED")
        value = {
            "formatVersion": 1,
            "revision": str(uuid.uuid4()),
            "policyRevision": policy["revision"],
            "enabled": True,
            "utcDays": days,
            "startMinute": start,
            "durationMinutes": duration,
            "maximumDownloadBytes": maximum,
            "keySha256": "0" * 64,
        }
        validate(value)
        export = export.absolute()
        reject_links(export)
        if export.is_relative_to(target.resolve()):
            raise ValueError("E_UPDATE_AUTOMATIC_EXPORT")
        if not review(
            {
                **value,
                "timezone": "UTC",
                "backupKeyExport": str(export),
                "mayFinishOutsideWindow": True,
                "automaticDataRewind": False,
            }
        ):
            raise ValueError("E_CONFIRMATION")
        directory = target / ".maintenance-secrets"
        reject_links(directory)
        if not directory.exists():
            if os.name == "nt":
                from windows_security import create_private_directory

                create_private_directory(directory)
            else:
                directory.mkdir(mode=0o700)
        selected = target / KEY
        reject_links(selected)
        if not selected.exists():
            raw = (secrets.token_hex(32) + "\n").encode()
            with private_output(selected, directory) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        value["keySha256"] = sha256(selected)
        # Verify ownership before exporting or enabling; no password is journaled.
        raw = (password(installation, value) + "\n").encode()
        if export.exists():
            # A registration interrupted after the exclusive export can resume;
            # never replace an unrelated file, even on an explicit retry.
            if (
                not export.is_file()
                or export.stat().st_size != len(raw)
                or sha256(export) != value["keySha256"]
            ):
                raise ValueError("E_UPDATE_AUTOMATIC_EXPORT")
        else:
            with private_output(export, directory) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        old = installation.state.get("automaticUpdatePolicy")
        if old is not None:
            validate(old)
            if all(old[name] == value[name] for name in value if name != "revision"):
                value = old
        # Remove the old *owned* schedule before changing its fixed definition.
        operate(installation, "remove")
        installation.state["automaticUpdatePolicy"] = value
        installation.save()
        installation.state["updateSchedule"] = operate(installation, "register")
        installation.save()
        return {
            "enabled": True,
            "timezone": "UTC",
            "keyExported": True,
            "policyRevision": value["policyRevision"],
            "revision": value["revision"],
        }


def disable(target: Path) -> dict:
    from operational_restore import require_admin
    from update_schedule import operate
    from update_worker import require_worker, validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        value = installation.state.get("automaticUpdatePolicy")
        if value is None:
            return {"enabled": False}
        validate(value)
        require_worker(installation, installation.state["updatePolicy"])
        operate(installation, "remove")
        value["enabled"] = False
        installation.save()
        installation.state["updateSchedule"] = operate(installation, "register")
        installation.save()
        return {"enabled": False, "backupKeyPreserved": True}


def run(target: Path) -> dict:
    """Called by the existing privileged worker after host/worker verification."""
    from update_download import download
    from update_gate import FINAL
    from update_transaction import apply, resume

    with installation_lock(target):
        installation = load_installation(target, verify=False)
        require_active(installation.state, update=True)
        value = copy.deepcopy(installation.state.get("automaticUpdatePolicy"))
        if value is None:
            return {"automatic": False}
        validate(value)
        transaction = installation.state.get("updateTransaction")
        pending = transaction is not None and transaction.get("phase") not in FINAL
        if pending:
            if (
                transaction.get("actor") != "AUTOMATIC"
                or transaction.get("automaticApproval") != value
            ):
                raise ValueError("E_UPDATE_AUTOMATIC_MANUAL")
            approved(installation, value, starting=False)
        elif not value["enabled"] or not in_window(value):
            return {"automatic": False, "outsideWindowOrDisabled": True}
        else:
            approved(installation, value, starting=True)
        key = password(installation, value)
    if pending:
        return resume(target, key, automatic=value)
    outcome = download(
        target,
        review=lambda summary: summary["totalBytes"] <= value["maximumDownloadBytes"],
    )
    if not outcome.get("updateAvailable", True):
        return outcome
    return apply(target, key, review=lambda _: True, automatic=value)
