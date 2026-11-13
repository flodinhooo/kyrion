"""Actual repeated source-image retention; disposable container is never started."""

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from update_compose import Compose


def verify(executable, image):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("E_FIXTURE_IMAGE_ID")

    def run(*arguments, **_options):
        result = subprocess.run(
            [str(executable), "--context", "default", *arguments],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if result.returncode:
            raise ValueError("E_FIXTURE_DOCKER")
        return result.stdout

    endpoint = json.loads(run("context", "inspect", "default"))[0]["Endpoints"][
        "docker"
    ]["Host"]
    if (
        not endpoint.startswith(("unix://", "npipe:////./pipe/"))
        or run("info", "--format", "{{.OSType}}").strip() != b"linux"
    ):
        raise ValueError("E_FIXTURE_LOCAL_ENGINE_REQUIRED")
    identifier = str(uuid.uuid4())
    name = "kyrion-update-" + identifier + "-caddy"
    if run("container", "ls", "-aq", "--filter", "name=^/" + name + "$").strip():
        raise ValueError("E_FIXTURE_CONTAINER_EXISTS")
    configuration = {
        "hostname": "synthetic.invalid",
        "address": "127.0.0.1",
        "release": "1.0.0",
        "manifestSha256": "a" * 64,
        "architecture": "linux/amd64",
    }
    adapter = object.__new__(Compose)
    adapter.installation = SimpleNamespace(
        state={
            "updateTransaction": {
                "formatVersion": 1,
                "id": identifier,
                "phase": "preparing",
                "directory": "transaction/" + uuid.UUID(identifier).hex[:16],
                "source": configuration,
                "target": configuration,
                "files": {
                    ".env": {"source": "a" * 64, "target": "b" * 64},
                    "compose.yml": {"source": "a" * 64, "target": "b" * 64},
                },
                "original": {"images": {"caddy": image}},
            }
        }
    )
    adapter.run = run
    try:
        adapter.retain()
        container = json.loads(run("container", "inspect", name))[0]
        anonymous = any(mount["Type"] == "volume" for mount in container["Mounts"])
        try:
            adapter.retain()
        except ValueError as error:
            if str(error) != "E_UPDATE_IMAGE_RETENTION":
                raise
            replay = False
        else:
            replay = True
        return {
            "actualDockerRetentionReplay": replay,
            "anonymousVolumesCreated": anonymous,
            "imageProcessExecuted": False,
            "servicesInstalled": False,
        }
    finally:
        if run("container", "ls", "-aq", "--filter", "name=^/" + name + "$").strip():
            container = json.loads(run("container", "inspect", name))[0]
            if (
                container["Image"] != image
                or container["State"]["Running"]
                or container["Config"]["Labels"].get("kyrion.update") != identifier
            ):
                raise ValueError("E_FIXTURE_CLEANUP_OWNER")
            # This invocation exclusively created the container without named
            # volumes/binds. Remove only its automatic anonymous empty volumes.
            run("container", "rm", "--volumes", name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.docker.resolve(), args.image)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    sys.exit(
        0
        if report["actualDockerRetentionReplay"]
        and not report["anonymousVolumesCreated"]
        else 1
    )
