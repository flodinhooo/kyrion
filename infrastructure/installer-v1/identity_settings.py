"""Public Core identity configuration, never a customer client secret."""

import ipaddress
import json
import re
from urllib.parse import urlsplit


def validate_identity(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "issuer",
        "clientId",
        "allowLoopbackHttp",
    }:
        raise ValueError("E_IDENTITY_CONFIG")
    issuer = value["issuer"]
    if (
        not isinstance(issuer, str)
        or len(issuer) > 512
        or not re.fullmatch(r"[A-Za-z0-9:/._-]+", issuer)
    ):
        raise ValueError("E_IDENTITY_CONFIG")
    try:
        url = urlsplit(issuer)
        loopback = (
            url.hostname == "localhost"
            or ipaddress.ip_address(url.hostname).is_loopback
        )
    except ValueError:
        loopback = False
    try:
        valid = (
            bool(url.hostname)
            and url.port != 0
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
        )
    except (ValueError, UnboundLocalError):
        valid = False
    if (
        not valid
        or issuer.endswith("/")
        or any(part in {".", ".."} for part in url.path.split("/"))
        or type(value["allowLoopbackHttp"]) is not bool
        or not (
        url.scheme == "https"
        or url.scheme == "http"
        and loopback
        and value["allowLoopbackHttp"]
    )
        or not isinstance(value["clientId"], str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", value["clientId"])
    ):
        raise ValueError("E_IDENTITY_CONFIG")
    return value.copy()


def configure_identity(installation, value: dict | None) -> list[str]:
    if value is None:
        return []
    value = validate_identity(value)
    previous = installation.state.get("identityProvider")
    if previous is not None and previous != value:
        raise ValueError("E_IDENTITY_CONFIG_CHANGED")
    installation.state["identityProvider"] = value
    installation.save()
    installation.write("identity-provider.json", json.dumps(value, sort_keys=True))
    return [
        "KYRION_CENTRAL_ENABLED=true",
        "KYRION_CENTRAL_ISSUER=" + value["issuer"],
        "KYRION_CENTRAL_CLIENT_ID=" + value["clientId"],
        "KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP=" + str(value["allowLoopbackHttp"]).lower(),
    ]
