"""Recheck this installer's managed files and live health, preserving failures."""

import argparse
import json
import os
from pathlib import Path

from host import reject_links, runtime_checks
from runtime import Installation, installation_lock, validate_inputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    target = parser.parse_args().target
    try:
        if os.name != "posix" or os.geteuid() != 0:
            raise ValueError("E_PRIVILEGE")
        reject_links(target)
        path = target / "install-state.json"
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size > 1024 * 1024
            or path.stat().st_mode & 0o077
            or path.stat().st_uid != 0
        ):
            raise ValueError("E_STATE")
        state = json.loads(path.read_text(encoding="utf-8"))
        config = state["configuration"]
        validate_inputs(target, config["hostname"], config["address"])
        with installation_lock(target):
            runtime_checks(config["address"], config["hostname"], fresh=False)
            installation = Installation(
                target,
                config,
                config["manifestSha256"],
                config["hostname"],
                config["address"],
            )
            installation.check_health()
        print(
            json.dumps(
                {"ok": True, "stage": "services-healthy", "ownerSetup": "not-verified"}
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"ok": False, "code": "E_VERIFY"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
