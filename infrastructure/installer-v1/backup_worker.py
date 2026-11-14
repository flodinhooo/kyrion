"""Consented, bounded operational backups over the existing capture/crypto path."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import backup_store as store
from authority import require_active
from backup_policy import slot, validate
from bundle import sha256, unique_object
from host import reject_links
from recovery import load_installation, verified_plaintext
from runtime import installation_lock
from update_gate import fenced
from update_worker import validate_host


def require_worker(installation, policy: dict, *, full=True) -> None:
    validate(policy)
    name = policy["workerFile"]
    digest = installation.state["files"].get(name)
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"[a-f0-9]{64}", digest)
        or name != "maintenance-" + digest[:32] + (".exe" if os.name == "nt" else "")
    ):
        raise ValueError("E_BACKUP_WORKER")
    selected = installation.target / name
    reject_links(selected)
    if sha256(selected) != digest:
        raise ValueError("E_BACKUP_WORKER")
    if os.name == "posix" and (
        selected.stat().st_uid != 0 or selected.stat().st_mode & 0o777 != 0o700
    ):
        raise ValueError("E_BACKUP_WORKER")
    if full:
        installation.verify_files()


def current_worker() -> tuple[str, bytes]:
    if not getattr(sys, "frozen", False):
        raise ValueError("E_BACKUP_FROZEN_REQUIRED")
    source = Path("/proc/self/exe") if os.name == "posix" else Path(sys.executable)
    with source.open("rb") as stream:
        raw = stream.read(128 * 1024**2 + 1)
    if not 64 <= len(raw) <= 128 * 1024**2 or (
        raw[:2] != b"MZ" if os.name == "nt" else raw[:4] != b"\x7fELF"
    ):
        raise ValueError("E_BACKUP_WORKER")
    name = (
        "maintenance-"
        + hashlib.sha256(raw).hexdigest()[:32]
        + (".exe" if os.name == "nt" else "")
    )
    return name, raw


def capability(path: Path, target: Path) -> None:
    if os.name == "nt":
        from windows_system import base_environment

        environment = base_environment()
    else:
        environment = {"PATH": "/usr/bin:/bin", "HOME": "/root", "LANG": "C"}
    result = subprocess.run(
        [str(path), "--capabilities"],
        cwd=target,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=30,
        **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
    )
    if result.returncode or len(result.stdout) > 16384:
        raise ValueError("E_BACKUP_WORKER")
    value = json.loads(result.stdout, object_pairs_hook=unique_object)
    if (
        not isinstance(value, dict)
        or type(value.get("backupProtocol")) is not int
        or value["backupProtocol"] != 1
    ):
        raise ValueError("E_BACKUP_FROZEN_REQUIRED")


def ensure_crypto(installation) -> None:
    directory = (
        installation.target / "payload/runtime/installer/gnupg/bin"
        if installation.state.get("backend") == "windows-native"
        else Path("/usr/bin")
    )
    suffix = ".exe" if installation.state.get("backend") == "windows-native" else ""
    if not all((directory / (name + suffix)).is_file() for name in ("gpg", "gpgconf")):
        raise ValueError("E_GPG_REQUIRED")


def validate_run(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "id",
            "policyRevision",
            "storeId",
            "configuration",
            "slot",
            "actor",
            "phase",
            "attempts",
            "name",
            "startedAt",
            "lastError",
        }
        or not isinstance(value.get("actor"), str)
        or value["actor"] not in {"AUTOMATIC", "MANUAL"}
        or not isinstance(value.get("phase"), str)
        or value["phase"] not in {"capturing", "verifying", "complete", "failed"}
        or type(value.get("attempts")) is not int
        or not 0 <= value["attempts"] <= 3
        or type(value.get("startedAt")) is not int
        or value["startedAt"] < 0
        or not isinstance(value.get("slot"), str)
        or len(value["slot"]) > 80
        or not isinstance(value.get("configuration"), dict)
        or set(value["configuration"])
        != {"hostname", "address", "release", "manifestSha256", "architecture"}
        or any(not isinstance(item, str) for item in value["configuration"].values())
        or (
            value.get("lastError") is not None
            and (
                not isinstance(value["lastError"], str)
                or not re.fullmatch(r"E_[A-Z_]{1,80}", value["lastError"])
            )
        )
    ):
        raise ValueError("E_BACKUP_RUN")
    try:
        if any(
            str(uuid.UUID(value[key])) != value[key]
            for key in ("id", "policyRevision", "storeId")
        ):
            raise ValueError()
        if value["name"] != "kyrion-" + uuid.UUID(value["id"]).hex + ".gpg":
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("E_BACKUP_RUN") from None


def configure(
    target: Path,
    *,
    destination: Path,
    export: Path,
    days: list[int],
    start: int,
    duration: int,
    keep: int,
    review,
) -> dict:
    from backup_schedule import operate
    from operational_restore import require_admin

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        old = installation.state.get("backupPolicy")
        if old is not None:
            validate(old)
            require_worker(installation, old)
        previous_run = installation.state.get("backupRun")
        if previous_run is not None:
            validate_run(previous_run)
            if previous_run["phase"] != "complete":
                raise ValueError("E_BACKUP_SCHEDULE_PENDING")
        destination = store.normalize(destination, target)
        export = store.export_path(installation, export, destination)
        name, raw = current_worker()
        ensure_crypto(installation)
        candidate = {
            "formatVersion": 1,
            "revision": str(uuid.uuid4()),
            "enabled": True,
            "workerFile": name,
            "utcDays": days,
            "startMinute": start,
            "durationMinutes": duration,
            "keep": keep,
            "store": {
                "path": str(destination),
                "id": str(uuid.uuid4()),
                "markerSha256": "0" * 64,
            },
            "keySha256": "0" * 64,
        }
        validate(candidate)
        if not review(
            {
                "destination": str(destination),
                "keyExport": str(export),
                "utcDays": days,
                "startMinute": start,
                "durationMinutes": duration,
                "keep": keep,
                "timezone": "UTC",
                "mayFinishOutsideWindow": True,
                "automaticRestore": False,
                "physicalOffHostCopyVerified": False,
            }
        ):
            raise ValueError("E_CONFIRMATION")
        binding = store.prepare(installation, destination)
        digest = store.prepare_key(installation, export, destination)
        installation.write(name, raw)
        if os.name == "posix":
            (target / name).chmod(0o700)
        capability(target / name, target)
        candidate.update(store=binding, keySha256=digest)
        if old is not None:
            validate(old)
            if all(
                old[field] == candidate[field]
                for field in candidate
                if field != "revision"
            ):
                candidate = copy.deepcopy(old)
            remove_schedule(installation)
        installation.state["backupPolicy"] = candidate
        installation.save()
        require_worker(installation, candidate)
        actual = operate(installation, "register")
        installation.state["backupSchedule"] = actual
        installation.save()
        if actual.get("state") != "registered":
            raise ValueError("E_BACKUP_SCHEDULE")
        return {
            "schedule": actual,
            "keyExported": True,
            "backupCreated": False,
            "policyRevision": candidate["revision"],
        }


def remove_schedule(installation) -> None:
    from backup_schedule import operate

    policy = installation.state.get("backupPolicy")
    if policy is None:
        return
    validate(policy)
    actual = operate(installation, "remove")
    policy["enabled"] = False
    installation.state["backupSchedule"] = actual
    installation.save()


def disable(target: Path) -> dict:
    from operational_restore import require_admin

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        remove_schedule(installation)
        return {"enabled": False, "externalBackupsRemoved": False, "keyRemoved": False}


def reset_incomplete(target: Path, *, review) -> dict:
    from operational_restore import require_admin

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        value = installation.state.get("backupRun")
        validate_run(value)
        if value["phase"] == "complete":
            raise ValueError("E_BACKUP_RUN")
        if not review(
            {
                "runId": value["id"],
                "phase": value["phase"],
                "filesRemoved": False,
                "servicesRecoveryRequired": installation.state.get(
                    "backupServiceRecovery"
                )
                is not None,
            }
        ):
            raise ValueError("E_CONFIRMATION")
        previous = installation.state.get("backupAbandoned", [])
        if not isinstance(previous, list):
            raise TypeError("E_BACKUP_RUN")
        installation.state["backupAbandoned"] = [*previous[-9:], copy.deepcopy(value)]
        installation.state.pop("backupRun")
        installation.save()
        return {"incompleteRunReset": True, "filesRemoved": False}


def capture(installation, destination: Path, password: str) -> None:
    if installation.state.get("backend") == "windows-native":
        from native_backup import capture as perform
    else:
        from recovery import capture as perform
    perform(
        installation,
        destination,
        password,
        scheduled_run=installation.state["backupRun"]["id"],
    )


def verify_capture(
    installation, destination: Path, password: str, expected: dict
) -> None:
    if installation.state.get("backend") == "windows-native":
        from native_runtime import admin_environment

        executable = installation.target / "payload/runtime/installer/gnupg/bin/gpg.exe"
        environment = admin_environment(installation.target)
    else:
        executable, environment = None, None
    with verified_plaintext(
        destination,
        password,
        executable=executable,
        environment=environment,
        private_parent=installation.target,
        security_source=installation.target if os.name == "nt" else None,
    ) as (_archive, manifest, _scratch):
        metadata = manifest["metadata"]
        if (
            metadata.get("installationId") != installation.state["installationId"]
            or metadata.get("configuration") != expected
            or metadata.get("scheduledBackupRunId")
            != installation.state["backupRun"]["id"]
        ):
            raise ValueError("E_BACKUP_CAPTURE_MISMATCH")


def run(target: Path, *, manual=False) -> dict:
    from operational_restore import require_admin

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target, verify=False)
        try:
            outcome = _run(installation, manual=manual)
        except (Exception, KeyboardInterrupt) as error:
            installation.state["backupAttempt"] = {
                "at": int(time.time()),
                "error": safe_error(error),
                "completed": False,
                "deferred": False,
                "outsideWindow": False,
                "alreadyCompletedSlot": False,
            }
            installation.save()
            raise
        installation.state["backupAttempt"] = {
            "at": int(time.time()),
            "error": None,
            "completed": outcome.get("completed") is True
            and not outcome.get("alreadyCompletedSlot"),
            "deferred": outcome.get("deferred") is True,
            "outsideWindow": outcome.get("outsideWindow") is True,
            "alreadyCompletedSlot": outcome.get("alreadyCompletedSlot") is True,
        }
        installation.save()
        return outcome


def safe_error(error) -> str:
    value = str(error).split(":", 1)[0]
    return value if re.fullmatch(r"E_[A-Z_]{1,80}", value) else "E_BACKUP_INTERRUPTED"


def recover_services(installation, *, manual=False) -> None:
    """Resolve an earlier pause independently of removable backup storage."""
    if installation.state.get("backupServiceRecovery") is None:
        return
    attempts = installation.state.get("backupServiceRecoveryAttempts", 0)
    if type(attempts) is not int or not 0 <= attempts <= 3:
        raise ValueError("E_BACKUP_SERVICE_JOURNAL")
    if attempts == 3 and not manual:
        raise ValueError("E_BACKUP_SERVICE_RECOVERY")
    installation.verify_files()
    installation.state["backupServiceRecoveryAttempts"] = min(attempts + 1, 3)
    installation.save()
    if installation.state.get("backend") == "windows-native":
        from native_backup import recover_service_state
    else:
        from recovery import recover_service_state
    recover_service_state(installation)
    installation.state.pop("backupServiceRecoveryAttempts", None)
    installation.save()


def _run(installation, *, manual=False) -> dict:
    if (
        fenced(installation.state)
        or installation.state.get("authority") is not None
        or installation.state.get("preparedForRestore")
        or installation.state.get("stage") == "uninstalled"
    ):
        return {"completed": False, "deferred": True}
    require_active(installation.state)
    recover_services(installation, manual=manual)
    from linux_crypto import require_complete

    require_complete(installation.state)
    policy = installation.state.get("backupPolicy")
    if policy is None:
        return {"completed": False, "configured": False}
    validate(policy)
    require_worker(installation, policy, full=False)
    if not manual and not policy["enabled"]:
        return {"completed": False, "disabled": True}
    current_slot = slot(policy)
    value = installation.state.get("backupRun")
    if value is not None:
        validate_run(value)
    pending = value is not None and value["phase"] != "complete"
    if not manual and not pending and current_slot is None:
        return {"completed": False, "outsideWindow": True}
    if pending and (
        value["policyRevision"] != policy["revision"]
        or value["storeId"] != policy["store"]["id"]
    ):
        raise ValueError("E_BACKUP_SCHEDULE_PENDING")
    if (
        not manual
        and not pending
        and value is not None
        and value["slot"] == current_slot
        and value["policyRevision"] == policy["revision"]
    ):
        return {"completed": True, "alreadyCompletedSlot": True}
    destination = store.verify(installation, policy["store"])
    store.prune(installation, policy["store"], policy["keep"])
    password = store.read_key(installation, policy["keySha256"])
    installation.verify_files()
    if not pending:
        if len(installation.state.get("backupHistory", [])) >= 1000:
            raise ValueError("E_BACKUP_HISTORY")
        identifier = str(uuid.uuid4())
        value = {
            "id": identifier,
            "policyRevision": policy["revision"],
            "storeId": policy["store"]["id"],
            "configuration": copy.deepcopy(installation.configuration),
            "slot": "manual:" + identifier if manual else current_slot,
            "actor": "MANUAL" if manual else "AUTOMATIC",
            "phase": "capturing",
            "attempts": 0,
            "name": "kyrion-" + uuid.UUID(identifier).hex + ".gpg",
            "startedAt": int(time.time()),
            "lastError": None,
        }
        installation.state["backupRun"] = value
        installation.save()
    if value["attempts"] >= 3:
        raise ValueError("E_BACKUP_SCHEDULE_ATTEMPTS")
    value["attempts"] += 1
    installation.save()
    selected = destination / value["name"]
    reject_links(selected)
    try:
        if not selected.exists():
            if installation.configuration != value["configuration"]:
                raise ValueError("E_BACKUP_SOURCE_CHANGED")
            value["phase"] = "capturing"
            installation.save()
            capture(installation, selected, password)
        value["phase"] = "verifying"
        installation.save()
        verify_capture(installation, selected, password, value["configuration"])
        receipt = {
            "runId": value["id"],
            "storeId": policy["store"]["id"],
            "name": value["name"],
            "sha256": sha256(selected),
            "bytes": selected.stat().st_size,
            "verifiedAt": int(time.time()),
        }
        store.validate_receipt(receipt)
        history = installation.state.get("backupHistory", [])
        if not isinstance(history, list) or any(
            item.get("runId") == value["id"] for item in history
        ):
            raise ValueError("E_BACKUP_HISTORY")
        installation.state["backupHistory"] = [*history, receipt]
        installation.state["backup"] = "encrypted-consistent-capture"
        value["phase"], value["lastError"] = "complete", None
        installation.state["backupRetentionError"] = None
        installation.save()
        store.prune(installation, policy["store"], policy["keep"])
        return {
            "completed": True,
            "runId": value["id"],
            "bytes": receipt["bytes"],
            "integrityVerified": True,
            "applicationRestoreVerified": False,
        }
    except (Exception, KeyboardInterrupt) as error:
        code = str(error).split(":", 1)[0]
        code = code if re.fullmatch(r"E_[A-Z_]{1,80}", code) else "E_BACKUP_INTERRUPTED"
        if value["phase"] == "complete":
            installation.state["backupRetentionError"] = code
        else:
            value["phase"], value["lastError"] = "failed", code
        installation.save()
        raise


def status(target: Path) -> dict:
    from backup_schedule import operate
    from operational_restore import require_admin

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target, verify=False)
        policy = installation.state.get("backupPolicy")
        if policy is None:
            return {"configured": False}
        validate(policy)
        value = installation.state.get("backupRun")
        if value is not None:
            validate_run(value)
        try:
            actual_schedule = operate(installation, "inspect")
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
            actual_schedule = {"state": "unverified", "coldBootVerified": False}
        try:
            store.verify(installation, policy["store"])
            store_available = True
        except (OSError, ValueError):
            store_available = False
        try:
            store.read_key(installation, policy["keySha256"])
            key_available = True
        except (OSError, ValueError):
            key_available = False
        attempt = installation.state.get("backupAttempt")
        if isinstance(attempt, dict):
            attempt = {
                "at": attempt.get("at") if type(attempt.get("at")) is int else None,
                "error": None
                if attempt.get("error") is None
                else safe_error(attempt["error"]),
                **{
                    key: attempt.get(key) is True
                    for key in (
                        "completed",
                        "deferred",
                        "outsideWindow",
                        "alreadyCompletedSlot",
                    )
                },
            }
        else:
            attempt = None
        return {
            "configured": True,
            "enabled": policy["enabled"],
            "timezone": "UTC",
            "utcDays": policy["utcDays"],
            "startMinute": policy["startMinute"],
            "durationMinutes": policy["durationMinutes"],
            "keep": policy["keep"],
            "destination": policy["store"]["path"],
            "schedule": actual_schedule,
            "storeAvailable": store_available,
            "keyAvailable": key_available,
            "deferredByUpdate": fenced(installation.state),
            "lastRunIsHistorical": True,
            "lastAttempt": attempt,
            "lastRun": None
            if value is None
            else {
                key: value[key]
                for key in ("id", "phase", "attempts", "lastError", "startedAt")
            },
            "retentionError": None
            if installation.state.get("backupRetentionError") is None
            else safe_error(installation.state["backupRetentionError"]),
            "applicationRestoreVerified": False,
        }


def configure_interactive(target: Path, messages: dict[str, str]) -> dict:
    from linux_crypto import interactive, needs_configuration

    if needs_configuration(target):
        result = interactive(target, messages)
        if not result["available"]:
            return {"configured": False, "cancelled": True}
    destination = Path(input(messages["backupScheduleDestination"] + ": ").strip())
    export = Path(input(messages["backupScheduleExport"] + ": ").strip())
    days = (
        input(messages["backupScheduleDays"] + " [1,2,3,4,5,6,7]: ").strip()
        or "1,2,3,4,5,6,7"
    )
    clock = input(messages["backupScheduleClock"] + " [03:00]: ").strip() or "03:00"
    duration = input(messages["backupScheduleDuration"] + " [120]: ").strip() or "120"
    keep = input(messages["backupScheduleKeep"] + " [7]: ").strip() or "7"
    if (
        not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", clock)
        or not duration.isdecimal()
        or not keep.isdecimal()
        or any(not day.strip().isdecimal() for day in days.split(","))
    ):
        raise ValueError("E_BACKUP_POLICY")

    def review(summary):
        print(messages["backupScheduleReview"])
        print(json.dumps(summary, ensure_ascii=True))
        return input("[CONFIGURE-BACKUPS/CANCEL]: ").strip() == "CONFIGURE-BACKUPS"

    return configure(
        target,
        destination=destination,
        export=export,
        days=[int(day.strip()) for day in days.split(",")],
        start=int(clock[:2]) * 60 + int(clock[3:]),
        duration=int(duration),
        keep=int(keep),
        review=review,
    )


def offer(target: Path, messages: dict[str, str]) -> None:
    if not getattr(sys, "frozen", False):
        return
    if (
        input(messages["backupScheduleOffer"] + " [CONFIGURE/skip]: ").strip()
        != "CONFIGURE"
    ):
        return
    print(json.dumps(configure_interactive(target, messages)))
