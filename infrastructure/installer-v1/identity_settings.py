"""Public Core identity configuration, never a customer client secret."""

import ipaddress
import json
import re
from urllib.parse import urlsplit

DEFAULT_ISSUER = "https://auth.kyrion.ch/realms/kyrion"
DEFAULT_CLIENT_ID = "kyrion-local"


def select_identity(
    issuer: str | None,
    client_id: str | None,
    *,
    saved: dict | None = None,
) -> dict:
    previous = validate_identity(saved) if saved is not None else None
    baseline = previous or {
        "issuer": DEFAULT_ISSUER,
        "clientId": DEFAULT_CLIENT_ID,
        "allowLoopbackHttp": False,
    }
    selected = validate_identity(
        {
            "issuer": issuer if issuer is not None else baseline["issuer"],
            "clientId": client_id if client_id is not None else baseline["clientId"],
            "allowLoopbackHttp": baseline["allowLoopbackHttp"],
        }
    )
    if previous is not None and selected != previous:
        raise ValueError("E_IDENTITY_CONFIG_CHANGED")
    return selected


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
        or not issuer.startswith(("https://", "http://"))
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
