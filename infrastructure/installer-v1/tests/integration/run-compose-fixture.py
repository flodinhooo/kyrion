"""Launch a real disposable Compose update fixture on the local Linux daemon.

The worker gets only a new VM-host directory and the rootful Docker socket.
All child bind mounts use that same absolute path. It never installs host units,
publishes a release, runs household actions, or prunes shared Docker resources.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path


def execute(docker, fixture):
    specification = json.loads((fixture / "fixture.json").read_bytes())
    identifier = specification["id"]
    if (
        specification.get("scope") != "installer-compose-fixture"
        or uuid.UUID(hex=identifier).hex != identifier
        or fixture.name != "compose-fixture-" + identifier
        or set(specification["images"]) != {"core-source", "core-target", "web"}
    ):
        raise ValueError("E_FIXTURE_SCOPE")

    def run(*arguments, timeout=120):
        result = subprocess.run(
            [str(docker), "--context", "default", *arguments],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        if result.returncode:
            raise ValueError("E_FIXTURE_DOCKER_LAUNCH")
        return result.stdout

    endpoint = json.loads(run("context", "inspect", "default"))[0]["Endpoints"][
        "docker"
    ]["Host"]
    if not endpoint.startswith(("unix://", "npipe:////./pipe/")) or not re.search(
        r"^Driver:\s+docker\s*$",
        run("buildx", "inspect", "default").decode(),
        re.MULTILINE,
    ):
        raise ValueError("E_FIXTURE_LOCAL_ENGINE_REQUIRED")
    run_id = uuid.uuid4().hex
    fixture = fixture / "runs" / run_id
    fixture.mkdir(parents=True, mode=0o700)
    specification["runId"] = run_id
    (fixture / "fixture.json").write_text(
        json.dumps(specification, indent=2), encoding="utf-8"
    )
    worker_name = "installer-fixture-worker-" + run_id
    worker_tag = "installer-fixture-worker:" + run_id
    if run(
        "image", "ls", "--filter", "reference=" + worker_tag, "--format", "{{.ID}}"
    ).strip():
        raise ValueError("E_FIXTURE_WORKER_EXISTS")
    context = fixture / "worker-context"
    context.mkdir(mode=0o700)
    source = Path(__file__).resolve().parents[2]
    for item in source.rglob("*"):
        if (
            not item.is_file()
            or "__pycache__" in item.parts
            or item.suffix not in {".py", ".ps1", ".json", ".yml", ".txt", ".mjs"}
            and item.name != "Caddyfile"
        ):
            continue
        if (
            item.is_symlink()
            or item.stat().st_size > 2 * 1024**2
            or any(part.startswith(".env") for part in item.relative_to(source).parts)
        ):
            raise ValueError("E_FIXTURE_PUBLIC_SOURCE")
        destination = context / "installer" / item.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, destination)
    (context / "Dockerfile").write_text(
        "FROM docker:29-cli AS client\nFROM debian:13-slim\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv libpython3.13 binutils gnupg openssl ca-certificates && rm -rf /var/lib/apt/lists/*\n"
        "COPY --from=client /usr/local/bin/docker /usr/local/bin/docker\n"
        "COPY --from=client /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins\n"
        "COPY installer /opt/installer\n"
        "RUN python3 -m venv /opt/test-python && /opt/test-python/bin/pip install --no-cache-dir -r /opt/installer/release/native-build-requirements.txt\n"
        "ENV PATH=/opt/test-python/bin:/usr/local/bin:/usr/bin:/bin\n",
        encoding="utf-8",
    )
    with (fixture / "worker-build.log").open("xb") as stream:
        built = subprocess.run(
            [
                str(docker),
                "--context",
                "default",
                "buildx",
                "build",
                "--builder",
                "default",
                "--load",
                "--platform",
                "linux/amd64",
                "--label",
                "kyrion.fixture.scope=" + identifier,
                "--tag",
                worker_tag,
                str(context),
            ],
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=1800,
            check=False,
        )
    if built.returncode:
        raise ValueError("E_FIXTURE_WORKER_BUILD")
    root = "/var/lib/installer-fixtures/" + run_id
    # A new exclusive marker distinguishes this leaf from any existing data.
    marker = (
        "import json,os,pathlib; p=pathlib.Path('/fixture'); os.chmod(p,0o700); f=p/'fixture.json'; h=f.open('x'); json.dump({'scope':'installer-compose-fixture','id':'"
        + identifier
        + "'},h); h.close()"
    )
    run(
        "run",
        "--rm",
        "--network",
        "none",
        "--volume",
        root + ":/fixture",
        worker_tag,
        "python",
        "-c",
        marker,
    )
    try:
        with (fixture / "transaction-run.log").open("xb") as stream:
            process = subprocess.run(
                [
                    str(docker),
                    "--context",
                    "default",
                    "run",
                    "--name",
                    worker_name,
                    "--label",
                    "kyrion.fixture.scope=" + identifier,
                    "--network",
                    "host",
                    "--add-host",
                    "fixture.test:127.0.0.1",
                    "--volume",
                    root + ":" + root,
                    "--volume",
                    "/var/run/docker.sock:/run/docker.sock",
                    "--mount",
                    "type=bind,source="
                    + str(fixture)
                    + ",target=/fixture-input,readonly",
                    "--env",
                    "KYRION_COMPOSE_FIXTURE=" + identifier,
                    worker_tag,
                    "python",
                    "-u",
                    "/opt/installer/tests/integration/verify-compose-transaction.py",
                    "--root",
                    root,
                    "--specification",
                    "/fixture-input/fixture.json",
                    "--report",
                    root + "/report.json",
                ],
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=2400,
                check=False,
            )
        if process.returncode:
            raise ValueError("E_FIXTURE_COMPOSE_TRANSACTION")
        raw = run(
            "run",
            "--rm",
            "--network",
            "none",
            "--volume",
            root + ":/fixture:ro",
            worker_tag,
            "cat",
            "/fixture/report.json",
        )
        report = json.loads(raw)
        (fixture / "report.json").write_bytes(raw)
        return report
    finally:
        # Cleanup is bounded by the root marker and exact project/transaction
        # labels read from our own root. Never enumerate or stop foreign apps.
        cleanup = r"""
import json,pathlib,subprocess,sys
root=pathlib.Path(sys.argv[1]); expected={'scope':'installer-compose-fixture','id':sys.argv[2]}
if json.loads((root/'fixture.json').read_bytes())!=expected: raise SystemExit('E_FIXTURE_CLEANUP_SCOPE')
journal=root/'installed/install-state.json'
if journal.exists():
 state=json.loads(journal.read_bytes()); project='kyrion-'+state['installationId']
 result=subprocess.run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project],check=True,capture_output=True,text=True)
 for name in result.stdout.split():
  item=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
  if item['Config']['Labels'].get('com.docker.compose.project')!=project: raise SystemExit('E_FIXTURE_CLEANUP_OWNER')
  subprocess.run(['docker','stop','--time','30',name],check=True,stdout=subprocess.DEVNULL)
  subprocess.run(['docker','rm',name],check=True,stdout=subprocess.DEVNULL)
 transaction=state.get('updateTransaction')
 if transaction:
  retained=subprocess.check_output(['docker','ps','-aq','--filter','label=kyrion.update='+transaction['id']],text=True).split()
  for name in retained:
   item=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
   if item['State']['Running'] or item['Config']['Labels'].get('kyrion.update')!=transaction['id']: raise SystemExit('E_FIXTURE_CLEANUP_OWNER')
   subprocess.run(['docker','rm',name],check=True,stdout=subprocess.DEVNULL)
 # Data stays private for explicit forensic inspection; no broad directory deletion.
"""
        run(
            "run",
            "--rm",
            "--network",
            "none",
            "--volume",
            root + ":" + root,
            "--volume",
            "/var/run/docker.sock:/run/docker.sock",
            worker_tag,
            "python",
            "-c",
            cleanup,
            root,
            identifier,
        )
        rows = run(
            "container", "ls", "-aq", "--filter", "name=^/" + worker_name + "$"
        ).strip()
        if rows:
            saved = json.loads(run("container", "inspect", worker_name))[0]
            if (
                saved["State"]["Running"]
                or saved["Config"]["Labels"].get("kyrion.fixture.scope") != identifier
            ):
                raise ValueError("E_FIXTURE_WORKER_CLEANUP_OWNER")
            run("container", "rm", worker_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.docker.resolve(), args.fixture.resolve())))
