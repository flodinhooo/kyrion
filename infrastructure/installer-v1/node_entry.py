"""Foreground prepared-node operations using the existing gateway implementation."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def run(args, messages: dict[str, str]) -> int:
    if not sys.platform.startswith("linux"):
        raise ValueError("E_AGENT_PLATFORM")
    if args.node_config is None:
        raise ValueError("E_NODE_CONFIG_REQUIRED")
    if not getattr(sys, "frozen", False):
        source_root = Path(__file__).resolve().parent
        component = source_root / "kyrion_gateway_agent/__init__.py"
        if not component.is_file() or (
            source_root.name == "installer-v1"
            and source_root.parent.name == "infrastructure"
        ):
            from package import source_file

            component = source_file(source_root, "kyrion_gateway_agent/__init__.py")
        if not component.is_file():
            raise ValueError("E_NODE_COMPONENT_MISSING")
        sys.path.insert(0, str(component.parent.parent))
    from kyrion_gateway_agent import client
    from kyrion_gateway_agent.config import AgentConfig
    from kyrion_gateway_agent.enrollment import (
        enroll_prepared,
        private_directory,
        read_private,
        runtime_lock,
    )
    from kyrion_gateway_agent.health import collect_health, platform_identity

    config_path = args.node_config.absolute()
    print(messages["nodeForegroundScope"])
    print(json.dumps({"configuration": str(config_path)}, ensure_ascii=True))
    if args.prepare_node:
        from host import inventory

        print(json.dumps(inventory(config_path.parent), ensure_ascii=True))
        digest = None
        supplied = (args.node_url, args.node_token_file, args.node_certificate)
        if any(value is not None for value in supplied) and not all(
            value is not None for value in supplied
        ):
            raise ValueError("E_NODE_ENROLL_INPUT")
        if all(value is not None for value in supplied):
            from host import reject_links

            reject_links(args.node_certificate)
            with args.node_certificate.open("rb") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError("E_AGENT_TLS_CONFIGURATION")
            digest = hashlib.sha256(raw).hexdigest()
            client.trusted_context(str(args.node_certificate.absolute()), digest)
            print(
                json.dumps(
                    {"coreUrl": args.node_url, "certificateSha256": digest},
                    ensure_ascii=True,
                )
            )
        elif not config_path.with_name(config_path.name + ".enrollment.json").is_file():
            raise ValueError("E_NODE_ENROLL_INPUT")
        print(messages["nodePairReview"])
        if input("[PAIR/CANCEL]: ").strip() != "PAIR":
            return 0
        config = enroll_prepared(
            config_path,
            url=args.node_url,
            token_file=args.node_token_file,
            certificate=args.node_certificate,
            expected_ca_sha256=digest,
            identity=platform_identity(),
        )
        print(messages["nodePaired"])
        print(
            json.dumps(
                {"nodeId": config.node_id, "enrolled": True, "serviceInstalled": False}
            )
        )
        return 0

    if any(
        value is not None
        for value in (args.node_url, args.node_token_file, args.node_certificate)
    ):
        raise ValueError("E_NODE_ENROLL_INPUT")
    if not config_path.is_file():
        raise ValueError("E_NODE_CONFIG_REQUIRED")
    private_directory(config_path.parent)
    read_private(config_path)
    config = AgentConfig.load(config_path)
    if (
        not config.local_only
        or config.ca_certificate is None
        or config.ca_sha256 is None
    ):
        raise ValueError("E_AGENT_TLS_CONFIGURATION")
    if getattr(args, "node_run", False):
        from kyrion_gateway_agent.cli import run_prepared

        print(messages["nodeRunReview"])
        if input("[RUN/CANCEL]: ").strip() != "RUN":
            return 0
        print(
            json.dumps(
                {
                    "nodeId": config.node_id,
                    "mode": "foreground",
                    "serviceInstalled": False,
                }
            )
        )
        with runtime_lock(config_path):
            run_prepared(config)
        return 0
    print(messages["nodeHeartbeatReview"])
    if input("[HEARTBEAT/CANCEL]: ").strip() != "HEARTBEAT":
        return 0
    client.heartbeat(config, collect_health())
    print(
        json.dumps(
            {
                "nodeId": config.node_id,
                "heartbeatAcknowledged": True,
                "serviceInstalled": False,
            }
        )
    )
    return 0
