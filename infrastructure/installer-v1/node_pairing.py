"""Private one-use transfer of the existing Core gateway enrollment."""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from bundle import unique_object
from host import reject_links
from node_entry import component

KIND = "kyrion-device-pairing"
LIMIT = 96 * 1024


@dataclass(frozen=True)
class Pairing:
    core_url: str
    certificate: str = field(repr=False)
    certificate_sha256: str
    enrollment_id: str
    expires_at: str
    token: str = field(repr=False)
    space_id: str
    installation_id: str

    def metadata(self) -> dict:
        return {
            "coreUrl": self.core_url,
            "certificateSha256": self.certificate_sha256,
            "enrollmentId": self.enrollment_id,
            "expiresAt": self.expires_at,
            "spaceId": self.space_id,
            "installationId": self.installation_id,
            "targetReachability": "not-yet-checked",
        }

    def document(self) -> dict:
        value = self.metadata()
        del value["targetReachability"]
        return {
            "formatVersion": 1,
            "kind": KIND,
            **value,
            "certificate": self.certificate,
            "enrollmentToken": self.token,
        }


def validate(value: object) -> Pairing:
    component(require_linux=False)
    from kyrion_gateway_agent.client import context_from_bytes
    from kyrion_gateway_agent.enrollment import core_url

    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "formatVersion",
            "kind",
            "coreUrl",
            "certificate",
            "certificateSha256",
            "enrollmentId",
            "expiresAt",
            "enrollmentToken",
            "spaceId",
            "installationId",
        }
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or value.get("kind") != KIND
    ):
        raise ValueError("E_NODE_PAIRING_FORMAT")
    if any(not isinstance(value[key], str) for key in value if key != "formatVersion"):
        raise ValueError("E_NODE_PAIRING_FORMAT")
    if (
        core_url(value["coreUrl"]) != value["coreUrl"]
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value["enrollmentToken"])
        or not re.fullmatch(r"[a-f0-9]{64}", value["certificateSha256"])
    ):
        raise ValueError("E_NODE_PAIRING_FORMAT")
    for key in ("enrollmentId", "spaceId", "installationId"):
        try:
            valid = str(uuid.UUID(value[key])) == value[key]
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("E_NODE_PAIRING_FORMAT")
    try:
        raw = value["certificate"].encode("ascii")
        expiry = datetime.datetime.fromisoformat(
            value["expiresAt"].replace("Z", "+00:00")
        )
    except (ValueError, UnicodeError) as error:
        raise ValueError("E_NODE_PAIRING_FORMAT") from error
    if (
        not raw
        or len(raw) > 65536
        or hashlib.sha256(raw).hexdigest() != value["certificateSha256"]
    ):
        raise ValueError("E_AGENT_TLS_CONFIGURATION")
    context_from_bytes(raw)
    if expiry.tzinfo is None or not value["expiresAt"].endswith("Z"):
        raise ValueError("E_NODE_PAIRING_FORMAT")
    remaining = (expiry - datetime.datetime.now(datetime.UTC)).total_seconds()
    if not 0 < remaining <= 630:
        raise ValueError("E_NODE_PAIRING_EXPIRED")
    return Pairing(
        value["coreUrl"],
        value["certificate"],
        value["certificateSha256"],
        value["enrollmentId"],
        value["expiresAt"],
        value["enrollmentToken"],
        value["spaceId"],
        value["installationId"],
    )


def load(path: Path | None) -> Pairing | None:
    if path is None:
        return None
    if os.name != "posix":
        raise ValueError("E_AGENT_PLATFORM")
    reject_links(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or (os.geteuid() != 0 and metadata.st_uid != os.geteuid())
            or metadata.st_mode & 0o077
            or metadata.st_nlink != 1
        ):
            raise ValueError("E_NODE_PAIRING_PRIVATE")
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("E_NODE_PAIRING_FORMAT")
    try:
        value = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as error:
        raise ValueError("E_NODE_PAIRING_FORMAT") from error
    return validate(value)


@contextlib.contextmanager
def materialize(args, pairing: Pairing | None):
    if pairing is None:
        yield args
        return
    # Materialize only after the caller's explicit PAIR/SERVICE confirmation.
    # Immutable parsed bytes prevent a source-file swap after review.
    validate(pairing.document())
    with tempfile.TemporaryDirectory(prefix="kyrion-pairing-") as directory:
        root = Path(directory)
        for name, raw in (
            ("code", pairing.token.encode("ascii")),
            ("ca.pem", pairing.certificate.encode("ascii")),
        ):
            with os.fdopen(
                os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        prepared = SimpleNamespace(**vars(args))
        prepared.node_pairing = None
        prepared.node_url = pairing.core_url
        prepared.node_token_file = root / "code"
        prepared.node_certificate = root / "ca.pem"
        prepared.node_ca_sha256 = pairing.certificate_sha256
        yield prepared


def configured_origin(installation) -> tuple[str, Path]:
    configuration = installation.configuration
    hostname = configuration["hostname"]
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", hostname):
        raise ValueError("E_NODE_PAIRING_ORIGIN")
    port = 443
    if installation.state.get("backend") == "windows-native":
        from native_roles import read_configuration

        port = read_configuration(installation.target)["ports"]["caddy"]
    return (
        "https://" + hostname + (":" + str(port) if port != 443 else ""),
        installation.target / "data/tls/cert.pem",
    )


def private_directory(path: Path) -> None:
    reject_links(path)
    if path.exists():
        raise ValueError("E_NODE_PAIRING_PRIVATE")
    elif os.name == "nt":
        from windows_security import create_private_directory

        create_private_directory(path)
    else:
        path.mkdir(mode=0o700)


def export(client, display_name: str) -> tuple[Path, Pairing]:
    if (
        not display_name
        or len(display_name) > 120
        or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in display_name)
    ):
        raise ValueError("E_DEVICE_NAME")
    installation = client.installation
    installation.verify_files()
    origin, certificate = configured_origin(installation)
    reject_links(certificate)
    with certificate.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("E_AGENT_TLS_CONFIGURATION")
    digest = hashlib.sha256(raw).hexdigest()
    component(require_linux=False)
    from kyrion_gateway_agent.client import CoreRequestError, prepared_capabilities

    # No owner/session credential is sent through the externally reachable route.
    try:
        prepared_capabilities(origin, str(certificate.absolute()), digest)
    except CoreRequestError as error:
        if error.status in {404, 405}:
            raise ValueError("E_NODE_PAIRING_INGRESS") from error
        raise
    space = client.request("GET", "/v1/space")
    if not isinstance(space, dict) or space.get("status") != "ACTIVE":
        raise ValueError("E_SPACE_UNAVAILABLE")
    space_id = str(uuid.UUID(space["id"]))
    destination = installation.target / ("pairing-transfer-" + uuid.uuid4().hex)
    private_directory(destination)
    enrollment = client.request(
        "POST", "/v1/gateways/enrollments", {"displayName": display_name}
    )
    if not isinstance(enrollment, dict) or set(enrollment) != {
        "id",
        "enrollmentToken",
        "expiresAt",
    }:
        raise ValueError("E_NODE_PAIRING_FORMAT")
    pairing = validate(
        {
            "formatVersion": 1,
            "kind": KIND,
            "coreUrl": origin,
            "certificate": raw.decode("ascii"),
            "certificateSha256": digest,
            "enrollmentId": enrollment["id"],
            "enrollmentToken": enrollment["enrollmentToken"],
            "expiresAt": enrollment["expiresAt"],
            "spaceId": space_id,
            "installationId": installation.state["installationId"],
        }
    )
    path = destination / "pairing.json"
    if os.name == "nt":
        from windows_security import open_secured_file

        descriptor = open_secured_file(path, destination)
    else:
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(
            (json.dumps(pairing.document(), ensure_ascii=True) + "\n").encode()
        )
        stream.flush()
        os.fsync(stream.fileno())
    if os.name == "posix":
        for directory in (destination, destination.parent):
            descriptor = os.open(
                directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    return path, pairing


def guided_export(client, messages):
    print(messages["nodePairingExportScope"])
    name = input(messages["devicesName"] + ": ").strip()
    if (
        input(messages["nodePairingExportReview"] + " [PAIR/CANCEL]: ").strip()
        != "PAIR"
    ):
        return
    path, pairing = export(client, name)
    print(messages["nodePairingExportSaved"])
    print(json.dumps({"file": str(path), **pairing.metadata()}, ensure_ascii=True))
