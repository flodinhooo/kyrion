"""Execute trusted old/new native workers against explicit compatibility fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import node_ingress
from runtime import Installation


def exercise(args):
    if os.geteuid() != 0 or not sys.platform.startswith("linux"):
        raise ValueError("E_FIXTURE_ROOT_LINUX_REQUIRED")
    for path, digest in (
        (args.old_worker, args.old_sha256),
        (args.worker, args.sha256),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("E_FIXTURE_WORKER_IDENTITY")
    target = args.work / ("ingress-workers-" + uuid.uuid4().hex)
    installation = Installation(
        target,
        {"release": "0.0.0-dev.worker-fixture", "architecture": "linux/amd64"},
        "a" * 64,
        "fixture.test",
        "127.0.0.1",
    )
    for worker, expected, old in (
        (args.old_worker, args.old_sha256, True),
        (args.worker, args.sha256, False),
    ):
        name = "maintenance-" + expected[:32]
        installation.write(name, worker.read_bytes())
        (target / name).chmod(0o700)
        installation.state["startupPolicy"] = {"enabled": True, "workerFile": name}
        installation.save()
        try:
            node_ingress.require_workers(installation)
        except ValueError as error:
            if not old or str(error) != "E_AGENT_INGRESS_WORKER":
                raise
        else:
            if old:
                raise ValueError("E_FIXTURE_OLD_WORKER_ACCEPTED")
    installation.state.pop("startupPolicy")
    installation.save()
    invoke = runpy.run_path(str(Path(__file__).with_name("verify-installer-node.py")))[
        "invoke"
    ]
    before = target / "old-format-diagnostics.json"
    code, _ = invoke(
        args.old_worker,
        ["--diagnostics", str(before), "--target", str(target)],
        b"en\nMAINTAIN\n",
        args.work,
    )
    if code or not before.is_file():
        raise ValueError("E_FIXTURE_OLD_FORMAT_BASELINE")
    installation.state.update(
        formatVersion=2,
        agentIngressTransition={"formatVersion": 1, "phase": "prepared"},
    )
    installation.save()
    after = target / "pending-format-diagnostics.json"
    code, output = invoke(
        args.old_worker,
        ["--diagnostics", str(after), "--target", str(target)],
        b"en\nMAINTAIN\n",
        args.work,
    )
    if code == 0 or after.exists() or b"E_RESUME" not in output:
        raise ValueError("E_FIXTURE_OLD_READER_NOT_FENCED")
    return {
        "actualOldNativeWorkerRejected": True,
        "actualNewNativeWorkerAccepted": True,
        "actualOldInstallerReadsCompletedFormat": True,
        "actualOldInstallerRefusesPendingFormat": True,
        "workerPolicyAndPendingMetadataAreExplicitFixtures": True,
        "scheduledTasksRegistered": False,
        "productionInstallationModified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old-worker", "worker", "work", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("old-sha256", "sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = exercise(args)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
