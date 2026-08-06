from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from kyrion_gateway_agent.client import CoreRequestError, enroll, heartbeat
from kyrion_gateway_agent.config import DEFAULT_CONFIG_PATH, AgentConfig
from kyrion_gateway_agent.health import collect_health, platform_identity

LOGGER = logging.getLogger("kyrion-gateway-agent")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kyrion gateway agent")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    enrollment = subparsers.add_parser("enroll")
    enrollment.add_argument("--core-url", required=True)
    enrollment.add_argument("--token", required=True)
    subparsers.add_parser("once")
    runner = subparsers.add_parser("run")
    runner.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "enroll":
        result = enroll(args.core_url, args.token, platform_identity())
        config = AgentConfig(args.core_url.rstrip("/"), result.node_id, result.gateway_token)
        config.save(args.config)
        LOGGER.info("Gateway enrollment completed for node %s", result.node_id)
        return

    config = AgentConfig.load(args.config)
    if args.command == "once":
        heartbeat(config, collect_health())
        LOGGER.info("Gateway heartbeat completed")
        return

    interval = max(5, min(args.interval, 60))
    while True:
        try:
            heartbeat(config, collect_health())
            LOGGER.info("Gateway heartbeat completed")
        except CoreRequestError as error:
            LOGGER.warning("Gateway heartbeat failed: %s", error)
        time.sleep(interval)


if __name__ == "__main__":
    main()
