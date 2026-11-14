"""Read-only actual host observations, filtered to non-identifying test evidence."""

import argparse
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from host import inventory, reject_links


def main(report: Path):
    reject_links(report)
    if report.exists() or not report.parent.is_dir():
        raise ValueError("E_TEST_REPORT")
    observed = inventory(report.parent)
    gpu = observed["gpu"]
    result = {
        "scope": "installer-read-only-hardware-development-observation",
        "actualOs": platform.system(),
        "architecture": observed["architecture"],
        "cpuDescriptionObserved": observed["cpu"] is not None,
        "cpuCount": observed["cpuCount"],
        "ramBytes": observed["ramBytes"],
        "adapters": [
            {
                key: row.get(key)
                for key in (
                    "source",
                    "vendor",
                    "dedicatedVramBytes",
                    "sharedMemoryLimitBytes",
                    "freeVramBytes",
                    "softwareAdapter",
                )
            }
            for row in gpu["adapters"]
        ]
        if gpu["adapters"] is not None
        else None,
        "nvidia": [
            {
                key: row.get(key)
                for key in (
                    "source",
                    "vendor",
                    "dedicatedVramBytes",
                    "freeVramBytes",
                    "driverVersion",
                )
            }
            for row in gpu["nvidia"]
        ]
        if gpu["nvidia"] is not None
        else None,
        "usableAcceleration": gpu["usableAcceleration"],
        "runtimeProbePerformed": gpu["runtimeProbePerformed"],
        "benchmarkMeasured": False,
        "configurationChanged": False,
    }
    with report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    main(parser.parse_args().report)
