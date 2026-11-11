#!/usr/bin/env python3
"""Read-only fresh-target checks, sharing the guided installer's host matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from host import inventory, reject_links

MIN_FREE = 12 * 1024**3
MIN_RAM = 4 * 1024**3


class PreflightError(ValueError):
    pass


def check(args: argparse.Namespace) -> dict:
    target = Path(args.install_dir)
    for path in (target, Path(args.data_dir), Path(args.secrets_dir)):
        reject_links(path)
        if path.exists():
            raise PreflightError("E_EXISTING_STATE: dedicated fresh target required")
    observed = inventory(target)
    if not observed["candidateProvisioning"]:
        raise PreflightError("E_PLATFORM: no supported candidate provisioning path")
    if observed["ramBytes"] is None or observed["ramBytes"] < MIN_RAM:
        raise PreflightError("E_MEMORY: at least 4 GiB known RAM required")
    if observed["freeBytes"] is None or observed["freeBytes"] < MIN_FREE:
        raise PreflightError("E_DISK: at least 12 GiB free required")
    if not all(observed["tools"].values()):
        raise PreflightError("E_TOOL: Docker, OpenSSL and systemd required")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--secrets-dir", required=True)
    parser.add_argument("--hostname", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps({"ok": True, "checks": check(args)}, sort_keys=True))
        return 0
    except (OSError, ValueError):
        print(json.dumps({"ok": False, "code": "E_PREFLIGHT"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
