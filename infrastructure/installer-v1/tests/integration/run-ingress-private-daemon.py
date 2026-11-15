"""Run Compose acceptance in a fresh owned Docker daemon and private namespaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host import reject_links
from update_worker import validate_host


def run(args):
    if os.geteuid() != 0 or not sys.platform.startswith("linux"):
        raise ValueError("E_FIXTURE_ROOT_LINUX_REQUIRED")
    validate_host(args.work)
    for path in (args.images, args.image_plan, args.daemon):
        reject_links(path)
    with args.images.open("rb") as archive:
        if hashlib.file_digest(archive, "sha256").hexdigest() != args.images_sha256:
            raise ValueError("E_FIXTURE_IMAGE_ARCHIVE")
    if (
        not args.daemon.is_file()
        or args.daemon.stat().st_uid != 0
        or args.daemon.stat().st_mode & 0o022
    ):
        raise ValueError("E_FIXTURE_DAEMON")
    scope = args.work / ("private-daemon-" + uuid.uuid4().hex)
    scope.mkdir(mode=0o700)
    (scope / "fixture.json").write_text(
        json.dumps({"scope": "installer-ingress-private-daemon"}), encoding="utf-8"
    )
    # The worker itself must run inside the namespaces, not just the daemon.
    if not args.inside:
        hosts = scope / "hosts"
        hosts.write_bytes(
            Path("/etc/hosts").read_bytes() + b"\n10.231.0.1 fixture.test\n"
        )
        command = [
            "/usr/bin/unshare",
            "--mount",
            "--net",
            "--propagation",
            "private",
            "/bin/sh",
            "-c",
            (
                'set -eu; /usr/bin/mount --bind "$1" /etc/hosts; /usr/sbin/ip link set lo up; '
                '/usr/sbin/ip addr add 10.231.0.1/32 dev lo; shift; exec "$@"'
            ),
            "ingress-private-daemon",
            str(hosts),
            sys.executable,
            str(Path(__file__).resolve()),
            "--inside",
            "--work",
            str(scope),
            "--images",
            str(args.images),
            "--images-sha256",
            args.images_sha256,
            "--image-plan",
            str(args.image_plan),
            "--daemon",
            str(args.daemon),
            "--report",
            str(args.report),
        ]
        child = subprocess.Popen(command, start_new_session=True)
        try:
            if child.wait(timeout=1200):
                raise ValueError("E_FIXTURE_PRIVATE_NAMESPACE")
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
                try:
                    child.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=15)
            raise
        return
    for namespace in ("mnt", "net"):
        if (
            Path("/proc/self/ns/" + namespace).stat().st_ino
            == Path("/proc/1/ns/" + namespace).stat().st_ino
        ):
            raise ValueError("E_FIXTURE_PRIVATE_NAMESPACE_REQUIRED")
    runtime = Path("/run") / ("kyrion-ingress-" + uuid.uuid4().hex[:12])
    runtime.mkdir(mode=0o700)
    endpoint = "unix://" + str(runtime / "docker.sock")
    environment = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "HOME": "/root",
        "DOCKER_HOST": endpoint,
        "DOCKER_CONFIG": str(scope / "docker-config"),
    }
    (scope / "docker-config").mkdir(mode=0o700)
    process = containerd = None
    try:
        with (scope / "daemon.log").open("wb") as log:
            executable = Path("/usr/bin/containerd")
            reject_links(executable)
            if executable.stat().st_uid != 0 or executable.stat().st_mode & 0o022:
                raise ValueError("E_FIXTURE_CONTAINERD")
            configuration = scope / "containerd.toml"
            configuration.write_text(
                'version = 2\ndisabled_plugins = ["io.containerd.grpc.v1.cri"]\n'
                + "root = "
                + json.dumps(str(scope / "containerd"))
                + "\n"
                + "state = "
                + json.dumps(str(runtime / "containerd"))
                + "\n"
                + "[grpc]\naddress = "
                + json.dumps(str(runtime / "containerd.sock"))
                + "\n",
                encoding="utf-8",
            )
            containerd = subprocess.Popen(
                [str(executable), "--config", str(configuration)],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
            daemon_configuration = scope / "daemon.json"
            daemon_configuration.write_text("{}\n", encoding="utf-8")
            process = subprocess.Popen(
                [
                    str(args.daemon),
                    "--config-file",
                    str(daemon_configuration),
                    "--host",
                    endpoint,
                    "--data-root",
                    str(scope / "data"),
                    "--exec-root",
                    str(runtime / "exec"),
                    "--pidfile",
                    str(runtime / "daemon.pid"),
                    "--containerd",
                    str(runtime / "containerd.sock"),
                    "--containerd-namespace",
                    "kyrion-" + runtime.name.removeprefix("kyrion-ingress-"),
                ],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
            for _ in range(120):
                if process.poll() is not None or containerd.poll() is not None:
                    raise ValueError("E_FIXTURE_PRIVATE_DAEMON_START")
                try:
                    ready = subprocess.run(
                        ["/usr/bin/docker", "info", "--format", "{{.ID}}"],
                        env=environment,
                        capture_output=True,
                        check=False,
                        timeout=5,
                    )
                except subprocess.TimeoutExpired:
                    continue
                if ready.returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise ValueError("E_FIXTURE_PRIVATE_DAEMON_READINESS")
            # The real install runtime intentionally ignores caller Docker
            # environment overrides. Route its default socket inside this
            # private mount namespace too; never alter the host socket itself.
            default_socket = Path("/run/docker.sock")
            reject_links(default_socket)
            if not stat.S_ISSOCK(default_socket.stat().st_mode):
                raise ValueError("E_FIXTURE_DEFAULT_SOCKET")
            subprocess.run(
                [
                    "/usr/bin/mount",
                    "--bind",
                    str(runtime / "docker.sock"),
                    str(default_socket),
                ],
                check=True,
                timeout=10,
            )
            subprocess.run(
                [
                    "/usr/bin/mount",
                    "-t",
                    "tmpfs",
                    "-o",
                    "mode=700,size=16m",
                    "tmpfs",
                    "/root",
                ],
                check=True,
                timeout=10,
            )
            with (scope / "image-load.log").open("wb") as loaded:
                subprocess.run(
                    ["/usr/bin/docker", "load", "--input", str(args.images)],
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=loaded,
                    stderr=loaded,
                    check=True,
                    timeout=300,
                )
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("verify-agent-ingress-compose.py")),
                    "--image-plan",
                    str(args.image_plan),
                    "--work",
                    str(scope),
                    "--report",
                    str(args.report),
                ],
                env=environment,
                stdin=subprocess.DEVNULL,
                check=True,
                timeout=900,
            )
    finally:
        for child in (process, containerd):
            if child is not None and child.poll() is None:
                child.send_signal(signal.SIGTERM)
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=15)
        # Retain the marker-owned data/logs for diagnosis. Never prune/remove
        # anything from the original host daemon, its images or its projects.
        if not runtime.resolve().is_relative_to(
            Path("/run")
        ) or not runtime.name.startswith("kyrion-ingress-"):
            raise ValueError("E_FIXTURE_RUNTIME_SCOPE")
        reject_links(runtime)
        shutil.rmtree(runtime)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("work", "images", "image-plan", "daemon", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--images-sha256", required=True)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    run(parser.parse_args())
