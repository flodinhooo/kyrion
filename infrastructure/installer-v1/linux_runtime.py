"""Consented Linux runtime preparation; application provisioning remains in runtime."""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import linux_crypto
import linux_packages as packages
from authority import prepare_restore, require_active, require_prerequisites
from bundle import authenticated_review
from host import network_checks, reject_links, runtime_checks
from recovery import load_installation
from runtime import Installation, fresh_target, image_plan, installation_lock, preflight

if TYPE_CHECKING:
    from install_download import IndexAuthority


def protected_file(path: Path) -> None:
    reject_links(path)
    if not path.is_file():
        raise ValueError("E_LINUX_RUNTIME_TOOLS")
    for item in (path, *path.parents):
        if item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
            raise ValueError("E_LINUX_RUNTIME_OWNER")


def tools_ready(installation: Installation) -> bool:
    if not Path("/usr/bin/docker").is_file() or not any(
        Path(path).is_file() for path in ("/usr/sbin/dockerd", "/usr/bin/dockerd")
    ):
        return False
    for path in (Path("/usr/sbin/dockerd"), Path("/usr/bin/dockerd")):
        if path.is_file():
            protected_file(path)
    version = packages.run(installation, "docker", "--version")
    match = re.search(r"\bDocker version (\d+)\.", version)
    if match is None or int(match[1]) < 26:
        return False
    # A missing plugin is an ordinary prerequisite, not a successful probe.
    try:
        compose = packages.run(installation, "docker", "compose", "version", "--short")
    except ValueError as error:
        if str(error) == "E_CRYPTO_PACKAGE_OPERATION":
            return False
        raise
    return bool(
        re.fullmatch(r"v?2\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?\s*", compose)
    ) and linux_crypto.available(installation)


def service(installation: Installation) -> dict[str, str]:
    keys = {"LoadState", "ActiveState", "UnitFileState", "FragmentPath", "DropInPaths"}
    raw = packages.run(
        installation,
        "systemctl",
        "show",
        "docker.service",
        *("--property=" + name for name in sorted(keys)),
    )
    result = {}
    for line in raw.splitlines():
        if "=" not in line:
            raise ValueError("E_LINUX_RUNTIME_SERVICE")
        key, value = line.split("=", 1)
        if key not in keys or key in result:
            raise ValueError("E_LINUX_RUNTIME_SERVICE")
        result[key] = value
    if set(result) != keys or result["LoadState"] != "loaded":
        raise ValueError("E_LINUX_RUNTIME_SERVICE")
    return result


def verify_vendor_unit(installation: Installation, observed: dict[str, str]) -> None:
    if observed["DropInPaths"] or observed["UnitFileState"] not in {
        "enabled",
        "disabled",
    }:
        raise ValueError("E_LINUX_RUNTIME_CUSTOM_SERVICE")
    verify_vendor_file(installation, Path(observed["FragmentPath"]))


def verify_vendor_file(installation: Installation, fragment: Path) -> None:
    paths = {
        "/usr/lib/systemd/system/docker.service",
        "/lib/systemd/system/docker.service",
    }
    if str(fragment) not in paths or str(fragment.resolve()) not in paths:
        raise ValueError("E_LINUX_RUNTIME_CUSTOM_SERVICE")
    fragment = fragment.resolve()
    protected_file(fragment)
    owner = packages.run(installation, "dpkg-query", "-S", str(fragment)).strip()
    match = re.fullmatch(r"(docker\.io|docker-ce)(?::(?:amd64|arm64))?: (/.+)", owner)
    if match is None or Path(match[2]).resolve() != fragment:
        raise ValueError("E_LINUX_RUNTIME_CUSTOM_SERVICE")
    if runtime_file_differences(
        packages.run(installation, "dpkg", "--verify", match[1])
    ):
        raise ValueError("E_LINUX_RUNTIME_CUSTOM_SERVICE")


def runtime_file_differences(raw: str) -> bool:
    """Minimal Debian images intentionally omit non-executable package docs."""
    for line in raw.splitlines():
        missing = re.fullmatch(
            r"missing\s+(/usr/share/(?:doc|man|locale|lintian)/[^\x00-\x1f]+)", line
        )
        if missing is None or ".." in PurePosixPath(missing[1]).parts:
            return True
    return False


def configure_service(
    target: Path,
    *,
    review: Callable[[dict], bool],
    approved_manifest: str | None = None,
    restore_request: dict | None = None,
) -> dict:
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_prerequisites(installation.state, restore_request)
        installation.verify_files()
        packages.require_complete(installation.state)
        if approved_manifest is not None and (
            installation.configuration["manifestSha256"] != approved_manifest
            or installation.state.get("linuxRuntimeServiceConsent")
            != {"manifestSha256": approved_manifest, "approved": True}
        ):
            raise ValueError("E_REVIEW_CHANGED")
        observed = service(installation)
        healthy = (
            observed["ActiveState"] == "active"
            and observed["UnitFileState"] == "enabled"
        )
        if not healthy:
            # Do not rewrite/unmask custom units or daemon configurations. A
            # supported preconfigured active engine can still be reused below.
            verify_vendor_unit(installation, observed)
            if approved_manifest is None and not review(service_review()):
                raise ValueError("E_LINUX_RUNTIME_CANCELLED")
            installation.state["linuxRuntimeStartup"] = {
                "phase": "configuring",
                "coldBootVerified": False,
            }
            installation.save()
            packages.run(installation, "systemctl", "enable", "--now", "docker.service")
            observed = service(installation)
        if (
            observed["ActiveState"] != "active"
            or observed["UnitFileState"] != "enabled"
        ):
            raise ValueError("E_LINUX_RUNTIME_SERVICE")
        # Includes actual engine locality/Linux type, Compose, DNS and bind
        # checks. A registered service or successful package install is not it.
        from update_compose import Compose

        Compose(installation)  # Existing rootful local daemon/socket validation.
        runtime_checks(
            installation.configuration["address"],
            installation.configuration["hostname"],
            fresh=installation.state.get("stage") == "reviewed",
        )
        installation.state["linuxRuntimeStartup"] = {
            "phase": "verified-running",
            "coldBootVerified": False,
        }
        installation.save()
        return {"running": True, "enabledAtBoot": True, "coldBootVerified": False}


def service_review() -> dict:
    return {
        "step": "service",
        "unit": "docker.service",
        "enableAtSystemBoot": True,
        "startWithoutUserLogin": True,
        "existingDaemonConfigurationChanged": False,
        "existingContainersMayResume": True,
        "packageScriptsMayStartOrEnableEngine": True,
    }


def has_daemon_state() -> bool:
    for root in (Path("/etc/docker"), Path("/var/lib/docker")):
        reject_links(root)
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            return True
    return False


def systemd_available() -> bool:
    return Path("/proc/1/comm").read_text().strip() == "systemd"


def prepare(
    target: Path,
    bundle: Path,
    authority: Path | IndexAuthority,
    expected: str,
    hostname: str,
    address: str,
    *,
    review: Callable[[dict], bool],
    restore_request: dict | None = None,
) -> dict:
    """Called after INSTALL consent; preserve one existing installer journal."""
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    observed = preflight(target, hostname, address)
    if any(
        os.environ.get(name)
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG")
    ):
        raise ValueError("E_LINUX_RUNTIME_EXISTING")
    if not systemd_available():
        raise ValueError("E_LINUX_RUNTIME_SYSTEMD")
    selected = shutil.which("docker")
    if selected and Path(selected).resolve() != Path("/usr/bin/docker").resolve():
        raise ValueError("E_LINUX_RUNTIME_EXISTING")
    # Missing software with pre-existing daemon data/configuration is not a
    # clean host. Never adopt or replace that state via a package install.
    daemon_state = has_daemon_state() if not selected else False
    if daemon_state and not target.exists():
        raise ValueError("E_LINUX_RUNTIME_EXISTING")
    with installation_lock(target):
        checked = authenticated_review(bundle, authority)
        if (
            checked.manifest_sha256 != expected
            or checked.manifest["architecture"] != "linux/" + observed["architecture"]
        ):
            raise ValueError("E_REVIEW_CHANGED")
        image_plan(checked.manifest)
        if target.exists():
            validate_host(target)
            installation = Installation(
                target, checked.manifest, expected, hostname, address
            )
            require_active(installation.state, preparing=restore_request is not None)
            fresh_target(installation)  # Reject malformed progress before OS mutation.
        else:
            # Validate parent ownership before creating the root-private journal.
            validate_host(target.parent)
            network_checks(address, hostname, fresh=True)
            installation = Installation(
                target, checked.manifest, expected, hostname, address
            )
        if restore_request is not None:
            prepare_restore(installation, restore_request)
        origin = {"manifestSha256": expected, "initialDaemonStateEmpty": True}
        if daemon_state:
            saved = installation.state.get("runtimePrerequisite")
            packages.validate(saved, packages.RUNTIME)
            if (
                installation.state.get("linuxRuntimeOrigin") != origin
                or installation.state.get("stage") != "reviewed"
                or saved["phase"] != "installing"
            ):
                raise ValueError("E_LINUX_RUNTIME_EXISTING")
        elif not selected:
            if installation.state.get("linuxRuntimeOrigin") not in (None, origin):
                raise ValueError("E_REVIEW_CHANGED")
            installation.state["linuxRuntimeOrigin"] = origin
            installation.save()
        reserve = (
            sum(item["bytes"] for item in checked.manifest["artifacts"]) + 12 * 1024**3
        )
        if (
            selected
            and packages.run(installation, "docker", "context", "show").strip()
            != "default"
        ):
            raise ValueError("E_LINUX_RUNTIME_EXISTING")
        consent = installation.state.get("linuxRuntimeServiceConsent")
        expected_consent = {"manifestSha256": expected, "approved": True}
        if consent != expected_consent or installation.state.get("stage") != "reviewed":
            # Package maintainer scripts can enable/start Docker. Consent must
            # precede APT too, not merely our later explicit systemctl action.
            if not review(service_review()):
                raise ValueError("E_LINUX_RUNTIME_CANCELLED")
            installation.state["linuxRuntimeServiceConsent"] = expected_consent
            installation.save()
        crypto_pending = installation.state.get("cryptoPrerequisite")
        if crypto_pending is not None:
            packages.validate(crypto_pending, packages.CRYPTO)
        resume_crypto = (
            crypto_pending is not None and crypto_pending["phase"] != "complete"
        )
    if resume_crypto:
        crypto_outcome = linux_crypto.configure(
            target, review=review, restore_request=restore_request
        )
        if not crypto_outcome["available"]:
            raise ValueError("E_LINUX_RUNTIME_CANCELLED")
    if packages.supported():
        outcome = packages.configure(
            target,
            spec=packages.RUNTIME,
            ready=tools_ready,
            review=review,
            reserve=reserve,
            restore_request=restore_request,
        )
    else:
        # Preserve the original prepared-runtime candidate path; do not claim
        # an automatic package implementation for an unimplemented OS variant.
        outcome = {
            "available": True,
            "packagesChanged": False,
            "packageBootstrapSupported": False,
        }
    if not outcome["available"]:
        raise ValueError("E_LINUX_RUNTIME_CANCELLED")
    return {
        **outcome,
        **configure_service(
            target,
            review=review,
            approved_manifest=expected,
            restore_request=restore_request,
        ),
    }


def interactive(
    target: Path,
    bundle: Path,
    authority: Path | IndexAuthority,
    expected: str,
    hostname: str,
    address: str,
    messages: dict[str, str],
    *,
    restore_request: dict | None = None,
) -> dict:
    def review(summary):
        print(messages["linuxRuntimeReview"])
        print(json.dumps(summary, ensure_ascii=True))
        token = {
            "metadata": "REFRESH-METADATA",
            "install": "INSTALL-RUNTIME",
            "service": "CONFIGURE-DOCKER",
        }[summary["step"]]
        return input("[" + token + "/CANCEL]: ").strip() == token

    return prepare(
        target,
        bundle,
        authority,
        expected,
        hostname,
        address,
        review=review,
        restore_request=restore_request,
    )
