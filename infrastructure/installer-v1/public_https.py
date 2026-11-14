"""Public-download TLS bootstrap; pinned local Core TLS stays separate."""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
from pathlib import Path

from bundle import unique_object
from host import reject_links

ROOT = Path(__file__).resolve().parent / "public-ca"
VERSION = "2026.10.23"
BUNDLE_SHA256 = "2ef52ad56b4803e264045c915e55c236cbfa045b84b81efefc218a19eb44bd2b"
WHEEL_SHA256 = "e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1"


def bundle() -> tuple[Path, dict]:
    path, metadata = ROOT / "cacert.pem", ROOT / "metadata.json"
    try:
        for selected, limit in ((path, 1024**2), (metadata, 8192)):
            reject_links(selected)
            if not selected.is_file() or not 1 <= selected.stat().st_size <= limit:
                raise ValueError()
        with path.open("rb") as stream:
            raw = stream.read(1024**2 + 1)
        with metadata.open("rb") as stream:
            metadata_raw = stream.read(8193)
        if len(raw) > 1024**2 or len(metadata_raw) > 8192:
            raise ValueError()
        document = json.loads(metadata_raw, object_pairs_hook=unique_object)
        if (
            hashlib.sha256(raw).hexdigest() != BUNDLE_SHA256
            or not isinstance(document, dict)
            or type(document.get("formatVersion")) is not int
            or document["formatVersion"] != 1
            or document.get("version") != VERSION
            or document.get("project") != "certifi"
            or document.get("license") != "MPL-2.0"
            or document.get("sourceWheelSha256") != WHEEL_SHA256
            or document.get("bundleSha256") != BUNDLE_SHA256
            or type(document.get("bundleBytes")) is not int
            or document["bundleBytes"] != len(raw)
        ):
            raise ValueError()
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("E_PUBLIC_CA_BUNDLE") from None
    return path, {
        "version": VERSION,
        "sha256": BUNDLE_SHA256,
        "bytes": len(raw),
        "license": "MPL-2.0",
    }


def hashed_store_present(directory: str | None) -> bool:
    if directory is None:
        return False
    try:
        for index, path in enumerate(Path(directory).iterdir()):
            # A configured large/unknown store is not grounds to substitute it.
            if index >= 4096:
                return True
            if re.fullmatch(r"[0-9a-fA-F]{8}\.[0-9]+", path.name) and path.is_file():
                return True
    except OSError:
        raise ValueError("E_PUBLIC_CA_STORE") from None
    return False


def configured_context() -> tuple[ssl.SSLContext, str, int]:
    try:
        context = ssl.create_default_context()
        loaded = context.cert_store_stats()["x509_ca"]
        defaults = ssl.get_default_verify_paths()
        explicit = any(name in os.environ for name in ("SSL_CERT_FILE", "SSL_CERT_DIR"))
        if (
            loaded
            or explicit
            or defaults.cafile
            or hashed_store_present(defaults.capath)
        ):
            source = "explicit" if explicit else "system"
        else:
            path, _information = bundle()
            context.load_verify_locations(cafile=str(path))
            source = "bundled"
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise ValueError("E_PUBLIC_CA_STORE")
        return context, source, loaded
    except (ssl.SSLError, OSError):
        raise ValueError("E_PUBLIC_CA_STORE") from None


def context() -> ssl.SSLContext:
    # No certificate/hostname failure is caught/retried through another context.
    return configured_context()[0]


def status() -> dict:
    result = {"connectionTested": False}
    try:
        _path, metadata = bundle()
        result.update({"bundleVerified": True, **metadata})
    except ValueError:
        return {
            "connectionTested": False,
            "bundleVerified": False,
            "error": "E_PUBLIC_CA_BUNDLE",
        }
    try:
        context, source, loaded = configured_context()
        result.update(
            {
                "trustSource": source,
                "systemCaCertificatesLoaded": loaded,
                "certificateVerificationRequired": context.verify_mode
                == ssl.CERT_REQUIRED,
                "hostnameVerificationRequired": context.check_hostname,
            }
        )
    except ValueError as error:
        code = str(error)
        result["error"] = (
            code
            if code in {"E_PUBLIC_CA_STORE", "E_PUBLIC_CA_BUNDLE"}
            else "E_PUBLIC_CA_STORE"
        )
    return result
