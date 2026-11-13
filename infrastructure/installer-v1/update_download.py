"""Verified release input staging. Download completion never means installation."""

from __future__ import annotations

import copy
import hashlib
import http.client
import json
import os
import re
import shutil
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

from authority import require_active
from bundle import ReviewedBundle, sha256, unique_object
from host import reject_links
from recovery import load_installation
from release_policy import NoRedirect, compatible_release, verify
from runtime import installation_lock

MAX_MANIFEST = 8 * 1024**2


def public_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("E_RELEASE_URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(ord(ch) < 33 for ch in value)
    ):
        raise ValueError("E_RELEASE_URL")
    return value


def open_download(url: str, offset: int = 0):
    headers = {"Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = "bytes=" + str(offset) + "-"
    request = urllib.request.Request(public_url(url), headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    return opener.open(request, timeout=20)


def manifest_bytes(url: str) -> bytes:
    with open_download(url) as response:
        if (
            response.status != 200
            or response.headers.get("Content-Encoding", "identity") != "identity"
        ):
            raise ValueError("E_DOWNLOAD_RESPONSE")
        raw = response.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise ValueError("E_NATIVE_MANIFEST_SIZE")
    return raw


def artifact_plan(raw: bytes, candidate: dict) -> list[dict]:
    """Bound paths and allocations before downloading; full bundle validation follows."""
    if (
        len(raw) > MAX_MANIFEST
        or hashlib.sha256(raw).hexdigest() != candidate["manifestSha256"]
    ):
        raise ValueError("E_DOWNLOAD_MANIFEST_DIGEST")
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    if (
        not isinstance(manifest, dict)
        or manifest.get("release") != candidate["version"]
        or manifest.get("architecture") != candidate["platform"]
    ):
        raise ValueError("E_UPDATE_COMPATIBILITY")
    native = candidate["platform"] == "windows/amd64"
    if type(manifest.get("schemaVersion")) is not int:
        raise ValueError("E_UPDATE_COMPATIBILITY")
    if native:
        compatibility = manifest.get("compatibility", {})
        components = manifest.get("components")
        if not isinstance(compatibility, dict) or not isinstance(components, dict):
            raise ValueError("E_UPDATE_COMPATIBILITY")
        if (
            manifest.get("schemaVersion") != 3
            or manifest.get("runtime") != "windows-native"
            or compatibility.get("schema") != candidate["targetSchema"]
            or type(compatibility.get("api")) is not int
            or not candidate["apiMin"] <= compatibility["api"] <= candidate["apiMax"]
            or any(
                not isinstance(components.get(name), dict)
                or components[name].get("version") != expected
                for name, expected in candidate["components"].items()
            )
        ):
            raise ValueError("E_UPDATE_COMPATIBILITY")
        items = [manifest.get("artifact")]
    else:
        if manifest.get("schemaVersion") != 1:
            raise ValueError("E_UPDATE_COMPATIBILITY")
        items = manifest.get("artifacts")
    if not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise ValueError("E_ARTIFACTS")
    names = set()
    maximum = 12 * 1024**3 if native else 64 * 1024**3
    for item in items:
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "bytes", "sha256"}
            or not isinstance(item["name"], str)
            or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.(?:tar|zip)", item["name"]
            )
            or item["name"].casefold() in names
            or type(item["bytes"]) is not int
            or not 0 < item["bytes"] <= maximum
            or not isinstance(item["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
            or native
            and item["name"] != "kyrion-windows-amd64.zip"
            or not native
            and not item["name"].endswith(".tar")
        ):
            raise ValueError("E_ARTIFACT")
        names.add(item["name"].casefold())
    if not native:
        from runtime import image_plan

        tags = image_plan(manifest)
        names = ("core", "web", "postgres", "caddy")
        expected = {
            name: next(
                tag.rsplit(":", 1)[1]
                for filename, tag in tags.items()
                if filename.startswith(("kyrion-" + name + "-", name + "-"))
            )
            for name in names
        }
        if candidate["components"] != expected:
            raise ValueError("E_UPDATE_COMPATIBILITY")
    public_url(candidate["manifestUrl"])
    return items


def stream_artifact(
    url: str,
    destination: Path,
    partial: Path,
    item: dict,
    *,
    security_source: Path | None = None,
    progress=None,
) -> None:
    reject_links(destination)
    reject_links(partial)
    if destination.exists():
        if (
            not destination.is_file()
            or destination.stat().st_size != item["bytes"]
            or sha256(destination) != item["sha256"]
        ):
            raise ValueError("E_DOWNLOAD_CHANGED")
        return
    if not partial.exists():
        if os.name == "nt":
            from windows_security import open_secured_file

            descriptor = open_secured_file(partial, security_source or partial.parent)
        else:
            descriptor = os.open(
                partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
        os.close(descriptor)
    if not partial.is_file() or partial.stat().st_size > item["bytes"]:
        raise ValueError("E_DOWNLOAD_CHANGED")
    deadline = time.monotonic() + 7200
    for _ in range(64):
        offset = partial.stat().st_size
        if offset == item["bytes"]:
            break
        if time.monotonic() >= deadline:
            raise ValueError("E_DOWNLOAD_TIMEOUT")
        with open_download(url, offset) as response:
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ValueError("E_DOWNLOAD_RESPONSE")
            if response.status == 200:
                start, end = 0, item["bytes"] - 1
            elif response.status == 206:
                match = re.fullmatch(
                    r"bytes ([0-9]+)-([0-9]+)/([0-9]+)",
                    response.headers.get("Content-Range", ""),
                )
                if match is None:
                    raise ValueError("E_DOWNLOAD_RANGE")
                start, end, total = map(int, match.groups())
                if (
                    start != offset
                    or not start <= end < total
                    or total != item["bytes"]
                ):
                    raise ValueError("E_DOWNLOAD_RANGE")
            else:
                raise ValueError("E_DOWNLOAD_RESPONSE")
            length = response.headers.get("Content-Length")
            remaining = end - start + 1
            if length is not None and (
                not length.isascii() or not length.isdigit() or int(length) != remaining
            ):
                raise ValueError("E_DOWNLOAD_RESPONSE")
            # Only a validated 200 response may restart the exact owned partial.
            with partial.open("r+b") as stream:
                if start == 0:
                    stream.truncate(0)
                stream.seek(start)
                while remaining:
                    try:
                        chunk = response.read(min(1024 * 1024, remaining))
                    except http.client.HTTPException:
                        raise ValueError("E_DOWNLOAD_INTERRUPTED") from None
                    if not chunk:
                        raise ValueError("E_DOWNLOAD_INTERRUPTED")
                    if len(chunk) > remaining:
                        raise ValueError("E_DOWNLOAD_RESPONSE")
                    stream.write(chunk)
                    remaining -= len(chunk)
                    if progress is not None:
                        progress(start + (end - start + 1) - remaining, item["bytes"])
                stream.flush()
                os.fsync(stream.fileno())
    if partial.stat().st_size != item["bytes"]:
        raise ValueError("E_DOWNLOAD_INTERRUPTED")
    if sha256(partial) != item["sha256"]:
        partial.unlink()
        raise ValueError("E_DOWNLOAD_DIGEST")
    os.link(partial, destination, follow_symlinks=False)
    partial.unlink()


def validate_payload(root: Path, raw: bytes, candidate: dict) -> ReviewedBundle:
    if candidate["platform"] == "windows/amd64":
        from native_bundle import validate

        manifest = validate(root, raw)
    else:
        from bundle import validate
        from runtime import image_identity, image_plan

        manifest = validate(root, root / "manifest.json", raw)
        for name, tag in image_plan(manifest).items():
            image_identity(root / name, tag)
    return ReviewedBundle(manifest, hashlib.sha256(raw).hexdigest())


def download(target: Path, *, review, progress=None) -> dict:
    from build_identity import read_build
    from maintenance import check_updates
    from operational_restore import require_admin
    from update_worker import require_worker, validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        policy = copy.deepcopy(installation.state.get("updatePolicy"))
        require_worker(installation, policy)
    proofs = []
    result = check_updates(
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
        capture_proof=proofs.append,
        require_enabled=False,
    )
    if result["candidate"] is None:
        return {"updateAvailable": False, "installed": False}
    candidate = result["candidate"]
    raw = manifest_bytes(public_url(candidate["manifestUrl"]))
    items = artifact_plan(raw, candidate)
    summary = {
        "version": candidate["version"],
        "platform": candidate["platform"],
        "manifestSha256": candidate["manifestSha256"],
        "artifacts": items,
        "totalBytes": sum(item["bytes"] for item in items),
        "installed": False,
    }
    if not review(summary):
        raise ValueError("E_CONFIRMATION")
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        if (
            installation.state.get("updatePolicy") != policy
            or installation.state.get("updateCheck") != result
        ):
            raise ValueError("E_UPDATE_POLICY_CHANGED")
        if len(proofs) != 1:
            raise ValueError("E_SIGNED_DOCUMENT")
        relative = "update-input/" + candidate["manifestSha256"][:24]
        root = target / relative
        reject_links(root)
        old = installation.state.get("updateDownload", {})
        continuing = (
            old.get("directory") == relative
            and old.get("manifestSha256") == candidate["manifestSha256"]
        )
        # Never adopt an unexplained partial, even if its size looks plausible.
        for position, item in enumerate(items):
            partial = root / ("artifact-" + str(position) + ".partial")
            reject_links(partial)
            if partial.exists() and not continuing:
                raise ValueError("E_DOWNLOAD_CHANGED")
        remaining_bytes = 0
        for position, item in enumerate(items):
            complete = root / item["name"]
            partial = root / ("artifact-" + str(position) + ".partial")
            reject_links(complete)
            existing = (
                complete.stat().st_size
                if complete.is_file()
                else partial.stat().st_size
                if partial.is_file()
                else 0
            )
            remaining_bytes += max(0, item["bytes"] - min(item["bytes"], existing))
        if shutil.disk_usage(target).free < remaining_bytes + 1024**3:
            raise ValueError("E_DOWNLOAD_DISK")
        proof_name = "index-" + hashlib.sha256(proofs[0]).hexdigest()[:12] + ".json"
        trust_raw = json.dumps(
            policy["trust"], sort_keys=True, separators=(",", ":")
        ).encode()
        trust_name = "trust-" + hashlib.sha256(trust_raw).hexdigest()[:12] + ".json"
        installation.write(relative + "/manifest.json", raw)
        installation.write(relative + "/" + proof_name, proofs[0])
        installation.write(relative + "/" + trust_name, trust_raw)
        state = {
            "formatVersion": 1,
            "directory": relative,
            "manifestSha256": candidate["manifestSha256"],
            "candidate": candidate,
            "policyRevision": policy["revision"],
            "indexProof": proof_name,
            "trustSnapshot": trust_name,
            "phase": "downloading",
            "lastError": None,
        }
        installation.state["updateDownload"] = state
        installation.save()
        try:
            for position, item in enumerate(items):
                stream_artifact(
                    urljoin(candidate["manifestUrl"], item["name"]),
                    root / item["name"],
                    root / ("artifact-" + str(position) + ".partial"),
                    item,
                    security_source=root,
                    progress=(
                        (
                            lambda done, total, name=item["name"]: progress(
                                name, done, total
                            )
                        )
                        if progress is not None
                        else None
                    ),
                )
            validate_payload(root, raw, candidate)
            state["phase"] = "verified"
            installation.save()
        except (OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
            code = str(error).split(":", 1)[0]
            state["lastError"] = (
                code
                if re.fullmatch(r"E_[A-Z_]{1,80}", code)
                else "E_DOWNLOAD_INTERRUPTED"
            )
            installation.save()
            raise
        return {
            **summary,
            "payloadVerified": True,
            "directory": str(root),
            "runtimeActivated": False,
        }


def revalidate(
    installation, installer_version: str, schema: int, api: int = 1
) -> ReviewedBundle:
    """Reauthorize staged inputs before a later transaction may use them."""
    from update_worker import require_worker

    require_active(installation.state)
    policy = installation.state.get("updatePolicy")
    require_worker(installation, policy)
    state = installation.state.get("updateDownload", {})
    if (
        type(state.get("formatVersion")) is not int
        or state["formatVersion"] != 1
        or state.get("phase") != "verified"
        or state.get("policyRevision") != policy["revision"]
    ):
        raise ValueError("E_UPDATE_POLICY_CHANGED")
    expected = "update-input/" + state.get("manifestSha256", "")[:24]
    if (
        not re.fullmatch(r"update-input/[a-f0-9]{24}", expected)
        or state.get("directory") != expected
    ):
        raise ValueError("E_DOWNLOAD_CHANGED")
    root = installation.target / expected
    for field, pattern in (
        ("indexProof", r"index-[a-f0-9]{12}\.json"),
        ("trustSnapshot", r"trust-[a-f0-9]{12}\.json"),
    ):
        if not isinstance(state.get(field), str) or not re.fullmatch(
            pattern, state[field]
        ):
            raise ValueError("E_DOWNLOAD_CHANGED")
    installation.verify_files()
    trust = json.loads(
        (root / state["trustSnapshot"]).read_bytes(), object_pairs_hook=unique_object
    )
    if trust != policy["trust"]:
        raise ValueError("E_UPDATE_POLICY_CHANGED")
    index = verify((root / state["indexProof"]).read_bytes(), trust, "release-index")
    candidate = compatible_release(
        index,
        installer_version,
        installation.configuration["release"],
        installation.configuration["architecture"],
        schema,
        api,
        installation.state.get("updateCheck", {}).get("sequence", 0),
    )
    if candidate != state.get("candidate") or candidate is None:
        raise ValueError("E_UPDATE_COMPATIBILITY")
    raw = (root / "manifest.json").read_bytes()
    artifact_plan(raw, candidate)
    return validate_payload(root, raw, candidate)
