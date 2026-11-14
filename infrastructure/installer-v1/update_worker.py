"""Finite installed release checks; no implicit installation or cloud fallback."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from authority import require_active
from build_identity import read_build
from host import reject_links
from recovery import load_installation
from release_policy import parse, validate_trust, version
from runtime import installation_lock


def validate_policy(policy: dict) -> None:
    if (
        not isinstance(policy, dict)
        or set(policy)
        != {"formatVersion", "revision", "enabled", "feed", "trust", "workerFile"}
        or type(policy["formatVersion"]) is not int
        or policy["formatVersion"] != 1
        or type(policy["enabled"]) is not bool
        or not isinstance(policy["revision"], str)
        or not isinstance(policy["feed"], str)
        or len(policy["feed"]) > 2048
        or not isinstance(policy["workerFile"], str)
        or not re.fullmatch(r"maintenance-[a-f0-9]{32}(?:\.exe)?", policy["workerFile"])
    ):
        raise ValueError("E_UPDATE_CONFIG")
    try:
        if str(uuid.UUID(policy["revision"])) != policy["revision"]:
            raise ValueError("E_UPDATE_CONFIG")
        url = urlsplit(policy["feed"])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.fragment
            or url.query
            or any(ord(ch) < 33 for ch in policy["feed"])
        ):
            raise ValueError("E_UPDATE_CONFIG")
    except ValueError:
        raise ValueError("E_UPDATE_CONFIG") from None
    validate_trust(policy["trust"])


def require_worker(installation, policy: dict) -> None:
    validate_policy(policy)
    name = policy["workerFile"]
    digest = installation.state["files"].get(name)
    if not isinstance(digest, str) or name != (
        "maintenance-" + digest[:32] + (".exe" if os.name == "nt" else "")
    ):
        raise ValueError("E_UPDATE_WORKER")
    installation.verify_files()
    if os.name == "posix":
        path = installation.target / name
        if path.stat().st_uid != 0 or path.stat().st_mode & 0o777 != 0o700:
            raise ValueError("E_UPDATE_WORKER")


def validate_host(target: Path) -> None:
    if os.name == "nt":
        from native_runtime import permissions

        permissions(target, "verify")
        return
    reject_links(target)
    for path in (target, *target.parents):
        if path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
            raise ValueError("E_UPDATE_HOST_OWNERSHIP")


def configure(
    target: Path, feed: str, trust_file: Path, expected_worker_sha256: str
) -> dict:
    from operational_restore import require_admin
    from update_schedule import operate

    require_admin()
    validate_host(target)
    # The worker must be a self-contained, versioned executable. A source Python
    # interpreter is never copied and presented as an end-user installer.
    if not getattr(sys, "frozen", False):
        raise ValueError("E_UPDATE_FROZEN_REQUIRED")
    try:
        version(read_build()["version"])
    except ValueError:
        raise ValueError("E_INSTALLER_UNRELEASED") from None
    reject_links(trust_file)
    if trust_file.stat().st_size > 256 * 1024:
        raise ValueError("E_TRUST_STORE")
    trust = parse(trust_file.read_bytes())
    source = Path(sys.executable)
    reject_links(source)
    if not 0 < source.stat().st_size <= 128 * 1024**2:
        raise ValueError("E_UPDATE_WORKER")
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_worker_sha256:
        raise ValueError("E_UPDATE_WORKER_CHANGED")
    name = "maintenance-" + digest[:32] + (".exe" if os.name == "nt" else "")
    candidate = {
        "formatVersion": 1,
        "revision": str(uuid.uuid4()),
        "enabled": True,
        "feed": feed,
        "trust": trust,
        "workerFile": name,
    }
    validate_policy(candidate)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        old = installation.state.get("updatePolicy")
        if old is not None:
            validate_policy(old)
            changed = any(
                old[field] != candidate[field]
                for field in ("feed", "trust", "workerFile")
            )
            if changed and old["enabled"]:
                # Refuse to overwrite a differently bound OS definition. Disable
                # it explicitly first; trust rotation is a separate signed flow.
                raise ValueError("E_UPDATE_POLICY_EXISTS")
            if not changed:
                candidate = old
                candidate["enabled"] = True
        installation.write(name, raw)
        if os.name == "posix":
            os.chmod(target / name, 0o700)
        installation.state["updatePolicy"] = candidate
        installation.save()
        require_worker(installation, candidate)
        actual = operate(installation, "register")
        installation.state["updateSchedule"] = actual
        if actual.get("state") != "registered":
            installation.save()
            raise ValueError("E_UPDATE_SCHEDULE")
        installation.state["updates"] = "checks-configured"
        installation.state.pop("updateSetupError", None)
        installation.save()
        return actual


def remove_schedule(installation) -> None:
    policy = installation.state.get("updatePolicy")
    if policy is None:
        return
    from update_schedule import operate

    require_worker(installation, policy)
    actual = operate(installation, "remove")
    policy["enabled"] = False
    installation.state["updateSchedule"] = actual
    installation.save()


def rotate_policy(target: Path, envelope: Path, expected_sha256: str) -> dict:
    from operational_restore import require_admin
    from release_policy import rotated_trust

    require_admin()
    validate_host(target)
    reject_links(envelope)
    if not envelope.is_file() or envelope.stat().st_size > 1024**2:
        raise ValueError("E_SIGNED_DOCUMENT_SIZE")
    raw = envelope.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("E_UPDATE_POLICY_CHANGED")
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        policy = copy.deepcopy(installation.state.get("updatePolicy"))
        require_worker(installation, policy)
        replacement = rotated_trust(policy["trust"], raw)
        policy["trust"] = replacement
        policy["revision"] = str(uuid.uuid4())
        installation.state["updatePolicy"] = policy
        installation.save()
        return {
            "trustEpoch": replacement["epoch"],
            "policyRevision": policy["revision"],
            "scheduleChanged": False,
        }


def run(target: Path) -> int:
    """Called by a fixed OS schedule. All output remains bounded machine state."""
    from maintenance import check_updates
    from operational_restore import require_admin

    require_admin()
    validate_host(target)
    from update_gate import fenced

    with installation_lock(target):
        installation = load_installation(target, verify=False)
        require_active(installation.state, update=True)
        pending = fenced(installation.state)
        if pending:
            from update_state import reconcile

            reconcile(installation)
        if installation.state.get("stage") == "uninstalled":
            return 0
        policy = copy.deepcopy(installation.state.get("updatePolicy"))
        validate_policy(policy)
        if not policy["enabled"]:
            return 0
        require_worker(installation, policy)
        has_automatic_policy = (
            installation.state.get("automaticUpdatePolicy") is not None
        )
    if pending:
        if not has_automatic_policy:
            return 2
        from update_automatic import run as automatic_run

        return automatic_attempt(target, automatic_run)
    try:
        check_updates(
            SimpleNamespace(
                target=target,
                installer_version=read_build()["version"],
                feed=policy["feed"],
                trust_store=None,
                installed_schema=None,
                installed_api=1,
            ),
            trusted_document=policy["trust"],
            policy_revision=policy["revision"],
        )
        error_code = None
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error).split(":", 1)[0]
        error_code = code if re.fullmatch(r"E_[A-Z_]{1,80}", code) else "E_UPDATE_CHECK"
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        # Never attribute a failure or clear a warning for a changed channel.
        if installation.state.get("updatePolicy") != policy:
            return 2
        installation.state["updateAttempt"] = {
            "at": int(time.time()),
            "policyRevision": policy["revision"],
            "error": error_code,
        }
        installation.save()
    if error_code is not None:
        return 2
    if not has_automatic_policy:
        return 0
    from update_automatic import run as automatic_run

    return automatic_attempt(target, automatic_run)


def automatic_attempt(target, operation) -> int:
    from update_gate import FINAL
    from update_state import PHASES

    error_code = None
    try:
        outcome = operation(target)
    except (OSError, ValueError, TypeError, KeyError) as error:
        code = str(error).split(":", 1)[0]
        error_code = (
            code if re.fullmatch(r"E_[A-Z_]{1,80}", code) else "E_UPDATE_AUTOMATIC"
        )
        outcome = None
    with installation_lock(target):
        installation = load_installation(target, verify=False)
        current = installation.state.get("updateTransaction")
        current = current if isinstance(current, dict) else {}
        phase = current.get("phase")
        completed = outcome is not None and outcome.get("complete") is True
        identifier = current.get("id")
        try:
            valid_identifier = (
                isinstance(identifier, str) and str(uuid.UUID(identifier)) == identifier
            )
        except (ValueError, AttributeError):
            valid_identifier = False
        if completed and (
            not valid_identifier
            or outcome.get("transactionId") != current.get("id")
            or outcome.get("phase") != phase
            or not isinstance(phase, str)
            or phase not in FINAL
        ):
            # A manual recovery or a new transaction can acquire the lock after
            # execution returned. Never attribute the old result to that state.
            error_code = "E_UPDATE_RESULT_CHANGED"
        installation.state["automaticUpdateAttempt"] = {
            "at": int(time.time()),
            "error": error_code,
            "phase": phase if isinstance(phase, str) and phase in PHASES else None,
            "completed": completed and error_code is None,
        }
        installation.save()
    return 0 if error_code is None else 2
