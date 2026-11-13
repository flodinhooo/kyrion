"""Public build-bound release-channel defaults; reuse installed update authority."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from build_identity import read_build
from bundle import sha256, unique_object
from host import reject_links
from release_policy import validate_trust, version

RESOURCE = "installer-channel.json"


def validate(document: dict) -> None:
    from cryptography.exceptions import UnsupportedAlgorithm

    if (
        not isinstance(document, dict)
        or set(document) != {"formatVersion", "feed", "trust"}
        or type(document.get("formatVersion")) is not int
        or document["formatVersion"] != 1
        or not isinstance(document.get("feed"), str)
        or not 1 <= len(document["feed"]) <= 2048
        or any(ord(char) < 33 for char in document["feed"])
    ):
        raise ValueError("E_INSTALLER_CHANNEL")
    try:
        url = urlsplit(document["feed"])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.fragment
            or url.query
        ):
            raise ValueError("E_INSTALLER_CHANNEL")
        validate_trust(document["trust"])
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        usages = set()
        for key in document["trust"]["keys"]:
            parsed = serialization.load_pem_public_key(key["pem"].encode("ascii"))
            if not isinstance(parsed, Ed25519PublicKey):
                raise TypeError("E_INSTALLER_CHANNEL")
            usages.update(key["usages"])
        if not {"release-index", "trust-rotation"} <= usages:
            raise ValueError("E_INSTALLER_CHANNEL")
    except (ValueError, TypeError, UnicodeError, UnsupportedAlgorithm):
        raise ValueError("E_INSTALLER_CHANNEL") from None


def document(path: Path) -> tuple[dict, bytes]:
    reject_links(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= 256 * 1024:
        raise ValueError("E_INSTALLER_CHANNEL")
    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=unique_object)
    validate(value)
    return value, raw


def stamp(root: Path, installer_version: str, channel: Path | None) -> dict:
    """Build only: production versions require an explicit operator channel."""
    try:
        version(installer_version)
        stable = True
    except ValueError:
        stable = False
    if stable and channel is None:
        raise ValueError("E_INSTALLER_CHANNEL_REQUIRED")
    identity = {"formatVersion": 1, "version": installer_version}
    if channel is not None:
        _, raw = document(channel)
        with (root / RESOURCE).open("xb") as stream:
            stream.write(raw)
        identity["releaseChannelSha256"] = hashlib.sha256(raw).hexdigest()
    (root / "installer-build.json").write_text(
        json.dumps(identity) + "\n", encoding="utf-8"
    )
    return identity


def embedded(root: Path | None = None, frozen: bool | None = None) -> dict | None:
    root = root if root is not None else Path(__file__).resolve().parent
    identity = read_build(root, frozen)
    path = root / RESOURCE
    expected = identity.get("releaseChannelSha256")
    if expected is None:
        if path.exists() or path.is_symlink():
            raise ValueError("E_INSTALLER_CHANNEL_UNBOUND")
        return None
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("E_INSTALLER_CHANNEL")
    value, raw = document(path)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("E_INSTALLER_CHANNEL_CHANGED")
    return value


def offer(target: Path, messages: dict[str, str]) -> None:
    """Called after setup releases its lock; no implicit automatic installation."""
    from recovery import load_installation
    from runtime import installation_lock
    from update_worker import configure

    channel = embedded()
    if channel is None:
        print(messages["updatesChannelUnavailable"])
        return
    with installation_lock(target):
        installation = load_installation(target)
        previous = installation.state.get("updatePolicy")
        if previous is not None and not (
            previous.get("enabled") is True
            and previous.get("feed") == channel["feed"]
            and previous.get("trust") == channel["trust"]
            and installation.state.get("updateSchedule", {}).get("state")
            != "registered"
        ):
            print(messages["updatesChannelExisting"])
            return
    print(messages["updatesChannelOffer"])
    print(
        json.dumps(
            {
                "feed": channel["feed"],
                "trustEpoch": channel["trust"]["epoch"],
                "automaticInstallation": False,
            }
        )
    )
    if input("[ENABLE-CHECKS/skip]: ").strip() != "ENABLE-CHECKS":
        return
    # configure reads a standalone trust document; stage it through the
    # existing protected journal, never trust a freshly downloaded key.
    with installation_lock(target):
        installation = load_installation(target)
        raw = json.dumps(channel["trust"], sort_keys=True).encode()
        name = "channel-trust-" + hashlib.sha256(raw).hexdigest()[:24] + ".json"
        installation.write(name, raw)
    try:
        configure(target, channel["feed"], target / name, sha256(Path(sys.executable)))
    except (OSError, ValueError) as error:
        code = str(error).split(":", 1)[0]
        with installation_lock(target):
            installation = load_installation(target)
            installation.state["updates"] = "schedule-not-configured"
            installation.state["updateSetupError"] = (
                code if re.fullmatch(r"E_[A-Z_]{1,80}", code) else "E_UPDATE_CONFIG"
            )
            installation.save()
        print(messages["updatesChannelFailed"])
        from error_guidance import guidance

        safe_code = code if re.fullmatch(r"E_[A-Z_]{1,80}", code) else "E_UPDATE_CONFIG"
        advice = guidance(safe_code, messages)
        if advice:
            print(advice)
        print(safe_code)
        return
    # Remove neither configured trust nor partial schedule state on interruption;
    # the existing configure command resumes registration idempotently.
    print(messages["updatesChannelConfigured"])


def summary(root: Path | None = None, frozen: bool | None = None) -> dict:
    value = embedded(root, frozen)
    return {
        "configured": value is not None,
        "feed": value["feed"] if value else None,
        "trustEpoch": value["trust"]["epoch"] if value else None,
        "sha256": read_build(root, frozen).get("releaseChannelSha256"),
    }
