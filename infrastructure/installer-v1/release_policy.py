"""Authenticated release/model documents, scoped trust rotation and compatibility."""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from bundle import unique_object
from host import reject_links
from runtime import atomic_json


class PolicyError(ValueError):
    pass


LIMIT = 1024 * 1024


def parse(raw: bytes) -> dict:
    if len(raw) > LIMIT:
        raise PolicyError("E_SIGNED_DOCUMENT_SIZE")
    result = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(result, dict):
        raise PolicyError("E_SIGNED_DOCUMENT")
    return result


def validate_trust(trust: dict) -> None:
    if (
        not isinstance(trust, dict)
        or set(trust) != {"formatVersion", "epoch", "keys"}
        or type(trust["formatVersion"]) is not int
        or trust["formatVersion"] != 1
        or type(trust["epoch"]) is not int
        or trust["epoch"] < 1
        or not isinstance(trust["keys"], list)
        or not 1 <= len(trust["keys"]) <= 16
    ):
        raise PolicyError("E_TRUST_STORE")
    ids = set()
    for key in trust["keys"]:
        if (
            not isinstance(key, dict)
            or set(key) != {"id", "pem", "notBefore", "notAfter", "usages"}
            or not isinstance(key["id"], str)
            or not re.fullmatch(r"[a-z0-9-]{1,80}", key["id"])
            or key["id"] in ids
            or not isinstance(key["pem"], str)
            or len(key["pem"]) > 16384
            or not key["pem"].startswith("-----BEGIN PUBLIC KEY-----")
            or type(key["notBefore"]) is not int
            or type(key["notAfter"]) is not int
            or key["notBefore"] >= key["notAfter"]
            or not isinstance(key["usages"], list)
            or not key["usages"]
            or any(
                not isinstance(usage, str)
                or usage not in {"release-index", "model-catalog", "trust-rotation"}
                for usage in key["usages"]
            )
        ):
            raise PolicyError("E_TRUST_STORE")
        ids.add(key["id"])
    if not any("trust-rotation" in key["usages"] for key in trust["keys"]):
        raise PolicyError("E_TRUST_ROTATION_KEY_REQUIRED")


def verify(
    envelope_bytes: bytes, trust: dict, usage: str, now: int | None = None
) -> dict:
    validate_trust(trust)
    envelope = parse(envelope_bytes)
    if set(envelope) != {"keyId", "payload", "signature"}:
        raise PolicyError("E_SIGNED_DOCUMENT")
    current = int(time.time()) if now is None else now
    key = next((key for key in trust["keys"] if key["id"] == envelope["keyId"]), None)
    if (
        key is None
        or usage not in key["usages"]
        or not key["notBefore"] <= current < key["notAfter"]
    ):
        raise PolicyError("E_TRUST_KEY")
    try:
        payload = base64.b64decode(envelope["payload"], validate=True)
        signature = base64.b64decode(envelope["signature"], validate=True)
    except (ValueError, TypeError):
        raise PolicyError("E_SIGNATURE") from None
    if len(signature) != 64 or len(payload) > LIMIT:
        raise PolicyError("E_SIGNATURE")
    try:
        from crypto_support import verify_ed25519

        verify_ed25519(payload, signature, key["pem"].encode("ascii"))
    except ImportError:
        if getattr(sys, "frozen", False):
            raise PolicyError("E_SIGNATURE_VERIFIER") from None
        with tempfile.TemporaryDirectory(prefix="kyrion-signature-") as directory:
            root = Path(directory)
            (root / "key.pem").write_text(key["pem"], encoding="ascii")
            (root / "payload").write_bytes(payload)
            (root / "signature").write_bytes(signature)
            try:
                result = subprocess.run(
                    [
                        "openssl",
                        "pkeyutl",
                        "-verify",
                        "-rawin",
                        "-pubin",
                        "-inkey",
                        str(root / "key.pem"),
                        "-sigfile",
                        str(root / "signature"),
                        "-in",
                        str(root / "payload"),
                    ],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise PolicyError("E_SIGNATURE_VERIFIER") from None
            if result.returncode:
                raise PolicyError("E_SIGNATURE")
    except ValueError:
        raise PolicyError("E_SIGNATURE") from None
    document = parse(payload)
    if (
        document.get("kind") != usage
        or type(document.get("expiresAt")) is not int
        or current >= document["expiresAt"]
    ):
        raise PolicyError("E_SIGNED_DOCUMENT_EXPIRED_OR_USAGE")
    return document


def rotated_trust(current: dict, envelope_bytes: bytes, now: int | None = None) -> dict:
    document = verify(envelope_bytes, current, "trust-rotation", now)
    replacement = document.get("replacement")
    if not isinstance(replacement, dict):
        raise PolicyError("E_TRUST_STORE")
    validate_trust(replacement)
    if replacement["epoch"] != current["epoch"] + 1:
        raise PolicyError("E_TRUST_ROLLBACK")
    return replacement


def rotate(trust_path: Path, envelope_bytes: bytes, now: int | None = None) -> dict:
    reject_links(trust_path)
    replacement = rotated_trust(parse(trust_path.read_bytes()), envelope_bytes, now)
    atomic_json(trust_path, replacement)
    return replacement


def version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value
    ):
        raise PolicyError("E_VERSION: stable semantic version required")
    return tuple(map(int, value.split(".")))


def compatible_release(
    index: dict,
    installer: str,
    installed: str,
    platform: str,
    schema: int,
    api: int,
    last_sequence: int = 0,
) -> dict | None:
    if (
        index.get("formatVersion") != 1
        or index.get("kind") != "release-index"
        or type(index.get("sequence")) is not int
        or index["sequence"] < last_sequence
        or not isinstance(index.get("releases"), list)
        or len(index["releases"]) > 1000
    ):
        raise PolicyError("E_RELEASE_INDEX")
    installer_version, installed_version = version(installer), version(installed)
    candidates = []
    seen = set()
    for entry in index["releases"]:
        if not isinstance(entry, dict) or set(entry) != {
            "version",
            "platform",
            "minimumInstaller",
            "fromSchemas",
            "targetSchema",
            "apiMin",
            "apiMax",
            "manifestUrl",
            "manifestSha256",
            "notesUrl",
            "components",
            "schemaDowngradeSupported",
        }:
            raise PolicyError("E_RELEASE_CONTRACT")
        selected_version = version(entry["version"])
        minimum = version(entry["minimumInstaller"])
        if not isinstance(entry["platform"], str):
            raise PolicyError("E_RELEASE_CONTRACT")
        key = (entry["version"], entry["platform"])
        if (
            key in seen
            or entry["platform"] not in {"linux/amd64", "linux/arm64", "windows/amd64"}
            or not isinstance(entry["fromSchemas"], list)
            or not entry["fromSchemas"]
            or any(type(item) is not int or item < 0 for item in entry["fromSchemas"])
            or any(
                type(entry[field]) is not int
                for field in ("targetSchema", "apiMin", "apiMax")
            )
            or entry["apiMin"] > entry["apiMax"]
            or entry["targetSchema"] < max(entry["fromSchemas"])
            or type(entry["schemaDowngradeSupported"]) is not bool
            or entry["schemaDowngradeSupported"]
            or not isinstance(entry["manifestSha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["manifestSha256"])
            or not isinstance(entry["components"], dict)
            or not {"core", "web", "postgres", "caddy"}.issubset(entry["components"])
            or any(
                not isinstance(item, str) or not item
                for item in entry["components"].values()
            )
        ):
            raise PolicyError("E_RELEASE_CONTRACT")
        for field in ("manifestUrl", "notesUrl"):
            if not isinstance(entry[field], str):
                raise PolicyError("E_RELEASE_URL")
            url = urlsplit(entry[field])
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.fragment
            ):
                raise PolicyError("E_RELEASE_URL")
        seen.add(key)
        if (
            entry["platform"] == platform
            and minimum <= installer_version
            and selected_version > installed_version
            and schema in entry["fromSchemas"]
            and entry["apiMin"] <= api <= entry["apiMax"]
        ):
            candidates.append(entry)
    return max(candidates, key=lambda entry: version(entry["version"]), default=None)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PolicyError("E_RELEASE_REDIRECT")


def fetch_document(url: str) -> bytes:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise PolicyError("E_RELEASE_URL")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(url, timeout=20) as response:
        raw = response.read(LIMIT + 1)
        if response.status != 200 or len(raw) > LIMIT:
            raise PolicyError("E_RELEASE_RESPONSE")
        return raw
