"""Validate real systemd unit syntax, without installing or starting any unit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from update_schedule import linux_plan


def verify(worker: Path, work: Path) -> dict:
    if sys.platform != "linux" or not worker.is_file() or not work.is_dir():
        raise ValueError("E_TEST_ENVIRONMENT")
    digest = hashlib.file_digest(worker.open("rb"), "sha256").hexdigest()
    with tempfile.TemporaryDirectory(
        prefix="kyrion-update-units-", dir=work
    ) as temporary:
        root = Path(temporary)
        name = "maintenance-" + digest[:32]
        shutil.copyfile(worker, root / name)
        os.chmod(root / name, 0o700)
        units = linux_plan(str(uuid.uuid4()), str(root), name)
        for filename, text in units.items():
            (root / filename).write_text(text, encoding="utf-8")
        result = subprocess.run(
            [
                "/usr/bin/systemd-analyze",
                "verify",
                "--man=no",
                *(str(root / filename) for filename in units),
            ],
            capture_output=True,
            check=False,
            timeout=30,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "SYSTEMD_LOG_LEVEL": "warning"},
        )
        if result.returncode:
            raise ValueError("E_TEST_SYSTEMD_SYNTAX")
    return {
        "actualSystemdDefinitionValidation": True,
        "workerSha256": digest,
        "unitsRegistered": False,
        "coldBootVerified": False,
        "workerExecutedBySystemd": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.worker, args.work)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
