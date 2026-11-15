"""Exact managed native proxy definitions for fresh setup and maintenance."""

from __future__ import annotations

from pathlib import Path

from node_transport import agent_handle


def configuration(root: Path, config: dict, *, agent: bool = True) -> str:
    header = (
        "{\n admin off\n persist_config off\n auto_https off\n}\nhttps://"
        + config["hostname"]
        + (
            ":" + str(config["ports"]["caddy"])
            if config["ports"]["caddy"] != 443
            else ""
        )
        + " {\n bind "
        + config["address"]
        + '\n tls "'
        + (root / "data/tls/cert.pem").as_posix()
        + '" "'
        + (root / "data/tls/key.pem").as_posix()
        + '"\n'
    )
    upstream = (
        " reverse_proxy https://127.0.0.1:"
        + str(config["ports"]["web"])
        + ' {\n transport http {\n tls_trust_pool file "'
        + (root / "web-cert.pem").as_posix()
        + '"\n }\n }\n'
    )
    if not agent:
        return header + upstream + "}\n"
    return (
        header
        + agent_handle(
            "https://127.0.0.1:" + str(config["ports"]["core"]), root / "core-cert.pem"
        )
        + " handle {\n"
        + upstream
        + " }\n}\n"
    )
