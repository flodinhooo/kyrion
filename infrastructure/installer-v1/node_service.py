"""Linux boot deployment of the existing prepared agent, using installer state."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

from authority import require_active
from bundle import sha256, unique_object
from host import reject_links
from linux_startup import machine_binding, worker_bytes
from runtime import Installation, installation_lock
from update_schedule import publish_unit, systemctl

BACKEND = "linux-prepared-node"


def enrollment_input(args) -> tuple[dict, bytes, bytes] | None:
    supplied = (args.node_url, args.node_token_file, args.node_certificate)
    if not any(value is not None for value in supplied):
        return None
    if not all(value is not None for value in supplied):
        raise ValueError("E_NODE_ENROLL_INPUT")
    from node_entry import component

    component()
    from kyrion_gateway_agent.client import trusted_context
    from kyrion_gateway_agent.enrollment import core_url

    for path in (args.node_token_file, args.node_certificate):
        reject_links(path)
    with args.node_token_file.open("rb") as stream:
        code = stream.read(1025)
    with args.node_certificate.open("rb") as stream:
        certificate = stream.read(65537)
    if not re.fullmatch(rb"[A-Za-z0-9_-]{43}\s*", code) or len(certificate) > 65536:
        raise ValueError("E_NODE_ENROLL_INPUT")
    digest = hashlib.sha256(certificate).hexdigest()
    if digest != args.node_ca_sha256:
        raise ValueError("E_AGENT_TLS_CONFIGURATION")
    trusted_context(str(args.node_certificate.absolute()), digest)
    return (
        {
            "url": core_url(args.node_url),
            "caSha256": digest,
            "codeSha256": hashlib.sha256(code.strip()).hexdigest(),
        },
        code,
        certificate,
    )


def read_owned(path: Path, uid: int, maximum: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != uid
            or metadata.st_mode & 0o077
            or metadata.st_nlink != 1
        ):
            raise ValueError("E_NODE_SERVICE_STATUS")
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("E_NODE_SERVICE_STATUS")
    return raw


def secure_root(path: Path, *, private=False) -> None:
    reject_links(path)
    for item in (path, *path.parents):
        metadata = item.stat()
        if metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise ValueError("E_NODE_SERVICE_PATH")
    if private and path.stat().st_mode & 0o027:
        raise ValueError("E_NODE_SERVICE_PATH")


def require_host(target: Path) -> None:
    if (
        not sys.platform.startswith("linux")
        or os.geteuid() != 0
        or not Path("/run/systemd/system").is_dir()
    ):
        raise ValueError("E_NODE_SYSTEMD_REQUIRED")
    if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+", str(target)):
        raise ValueError("E_TARGET")
    secure_root(target.parent)
    if target.exists():
        secure_root(target, private=True)


class NodeInstallation(Installation):
    def save(self) -> None:
        self.state.setdefault("backend", BACKEND)
        self.state.setdefault(
            "nodeMachine", machine_binding(self.state["installationId"])
        )
        super().save()

    def verify_files(self) -> None:
        for name, digest in self.state["files"].items():
            if not re.fullmatch(r"node-worker-[a-f0-9]{32}", name):
                raise ValueError("E_NODE_SERVICE_WORKER")
            path = self.target / name
            reject_links(path)
            if (
                not path.is_file()
                or path.stat().st_uid != 0
                or path.stat().st_mode & 0o027
                or sha256(path) != digest
                or path.stat().st_nlink != 1
            ):
                raise ValueError("E_NODE_SERVICE_WORKER")


def load(target: Path) -> NodeInstallation:
    require_host(target)
    path = target / "install-state.json"
    reject_links(path)
    if (
        not path.is_file()
        or path.stat().st_uid != 0
        or path.stat().st_mode & 0o077
        or path.stat().st_size > 1024 * 1024
    ):
        raise ValueError("E_STATE")
    state = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    if state.get("backend") != BACKEND:
        raise ValueError("E_NODE_PROFILE_OPERATION")
    configuration = state["configuration"]
    installation = NodeInstallation(
        target,
        configuration,
        configuration["manifestSha256"],
        configuration["hostname"],
        configuration["address"],
    )
    require_active(installation.state)
    if installation.state.get("nodeMachine") != machine_binding(
        installation.state["installationId"]
    ):
        raise ValueError("E_STARTUP_HOST_CHANGED")
    return installation


def identity(installation, *, create: bool) -> tuple[int, int, str]:
    import grp
    import pwd

    name = "kyrion-node-" + uuid.UUID(installation.state["installationId"]).hex[:16]
    home = str(installation.target / "agent")
    previous = installation.state.get("nodeAccount")
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        account = None
    if previous is None:
        if not create or account is not None:
            raise ValueError("E_NODE_SERVICE_IDENTITY")
        try:
            grp.getgrnam(name)
        except KeyError:
            pass
        else:
            raise ValueError("E_NODE_SERVICE_IDENTITY")
        installation.state["nodeAccount"] = {"name": name, "state": "creating"}
        installation.save()
        previous = installation.state["nodeAccount"]
    if previous.get("name") != name:
        raise ValueError("E_NODE_SERVICE_IDENTITY")
    if account is None:
        if not create or previous != {"name": name, "state": "creating"}:
            raise ValueError("E_NODE_SERVICE_IDENTITY")
        result = subprocess.run(
            [
                "/usr/sbin/useradd",
                "--system",
                "--user-group",
                "--no-create-home",
                "--home-dir",
                home,
                "--shell",
                "/usr/sbin/nologin",
                name,
            ],
            env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C"},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise ValueError("E_NODE_SERVICE_ACCOUNT")
        account = pwd.getpwnam(name)
    if (
        account.pw_uid == 0
        or account.pw_gid == 0
        or account.pw_dir != home
        or account.pw_shell != "/usr/sbin/nologin"
        or grp.getgrgid(account.pw_gid).gr_name != name
        or any(
            item.pw_uid == account.pw_uid and item.pw_name != name
            for item in pwd.getpwall()
        )
        or any(name in item.gr_mem for item in grp.getgrall())
    ):
        raise ValueError("E_NODE_SERVICE_IDENTITY")
    expected = {
        "name": name,
        "state": "ready",
        "uid": account.pw_uid,
        "gid": account.pw_gid,
    }
    if previous not in ({"name": name, "state": "creating"}, expected):
        raise ValueError("E_NODE_SERVICE_IDENTITY")
    if previous != expected:
        installation.state["nodeAccount"] = expected
        installation.save()
    return account.pw_uid, account.pw_gid, name


def definition(installation, worker: str, account: str) -> str:
    identifier = str(uuid.UUID(installation.state["installationId"]))
    target = str(installation.target)
    if (
        not re.fullmatch(r"/[A-Za-z0-9/_-]+", target)
        or not re.fullmatch(r"node-worker-[a-f0-9]{32}", worker)
        or account != "kyrion-node-" + uuid.UUID(identifier).hex[:16]
    ):
        raise ValueError("E_NODE_SERVICE_PLAN")
    return (
        "[Unit]\nDescription=Kyrion prepared node " + identifier + "\n"
        "After=network-online.target\nWants=network-online.target\n"
        "StartLimitIntervalSec=300\nStartLimitBurst=3\n\n[Service]\nType=simple\n"
        "User=" + account + "\nGroup=" + account + "\nUMask=0077\n"
        "ExecStart="
        + target
        + "/"
        + worker
        + " --background-node --node-config "
        + target
        + "/agent/agent.json\nWorkingDirectory="
        + target
        + "/agent\n"
        "Environment=PATH=/usr/bin:/bin\nEnvironment=LANG=C.UTF-8\n"
        "Restart=on-failure\nRestartSec=10s\nTimeoutStopSec=30s\nKillMode=control-group\n"
        "NoNewPrivileges=yes\nCapabilityBoundingSet=\nAmbientCapabilities=\n"
        "ProtectSystem=strict\nProtectHome=yes\nPrivateTmp=yes\nPrivateDevices=yes\n"
        "ProtectKernelTunables=yes\nProtectKernelModules=yes\nProtectControlGroups=yes\n"
        "RestrictSUIDSGID=yes\nRestrictRealtime=yes\nLockPersonality=yes\n"
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK\n"
        "ReadWritePaths=" + target + "/agent\n\n[Install]\nWantedBy=multi-user.target\n"
    )


def owned_unit(installation) -> Path:
    directory = Path("/etc/systemd/system")
    secure_root(directory)
    path = directory / (
        "kyrion-"
        + str(uuid.UUID(installation.state["installationId"]))
        + "-node.service"
    )
    reject_links(path)
    if path.exists() and (
        path.stat().st_uid != 0
        or path.stat().st_mode & 0o022
        or path.stat().st_nlink != 1
        or sha256(path) != installation.state.get("nodeUnitSha256")
    ):
        raise ValueError("E_NODE_SERVICE_UNIT")
    # Foreign drop-ins can change executable/privileges. Never activate them.
    if path.with_name(path.name + ".d").exists():
        raise ValueError("E_NODE_SERVICE_UNIT")
    return path


def run_as(installation, account: str, *arguments: str) -> bytes:
    worker = installation.state["nodeWorker"]
    installation.verify_files()
    result = subprocess.run(
        [
            "/usr/sbin/runuser",
            "-u",
            account,
            "--",
            str(installation.target / worker),
            *arguments,
        ],
        env={
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "HOME": str(installation.target / "agent"),
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=90,
        check=False,
    )
    if result.returncode or len(result.stdout) > 65536:
        raise ValueError("E_NODE_SERVICE_ENROLLMENT")
    return result.stdout


def service_state(installation) -> dict:
    uid, _, _ = identity(installation, create=False)
    unit = owned_unit(installation)
    result = {
        "backend": BACKEND,
        "unit": unit.name,
        "registered": unit.exists(),
        "enabled": False,
        "active": False,
        "coreConnection": "unknown",
        "coldBootVerified": False,
    }
    if unit.exists():
        values = dict(
            line.split("=", 1)
            for line in systemctl(
                "show",
                unit.name,
                "--property=ActiveState,UnitFileState,MainPID,FragmentPath,DropInPaths",
            ).splitlines()
            if "=" in line
        )
        if values.get("FragmentPath") != str(unit) or values.get("DropInPaths"):
            raise ValueError("E_NODE_SERVICE_UNIT")
        result.update(
            enabled=values.get("UnitFileState") == "enabled",
            active=values.get("ActiveState") == "active",
        )
        status = installation.target / "agent/runtime-status.json"
        reject_links(status)
        if result["active"] and status.is_file():
            metadata = status.stat()
            if (
                metadata.st_uid != uid
                or metadata.st_mode & 0o077
                or metadata.st_size > 8192
            ):
                raise ValueError("E_NODE_SERVICE_STATUS")
            observed = json.loads(
                read_owned(status, uid, 8192), object_pairs_hook=unique_object
            )
            from time import CLOCK_BOOTTIME, clock_gettime

            age = clock_gettime(CLOCK_BOOTTIME) - observed.get("observedBoottime", -1)
            pid = observed.get("pid")
            if type(pid) is int and pid > 1 and 0 <= age <= 40:
                process = Path("/proc") / str(pid)
                if process.is_dir() and process.stat().st_uid == uid:
                    # PyInstaller's bootloader is the main PID; Python is its child.
                    parent = (
                        (process / "stat").read_text().rsplit(") ", 1)[1].split()[1]
                    )
                    if str(pid) == values.get("MainPID") or parent == values.get(
                        "MainPID"
                    ):
                        state = observed.get("state")
                        if state not in {
                            "starting",
                            "connected",
                            "disconnected",
                            "stopped",
                        }:
                            raise ValueError("E_NODE_SERVICE_STATUS")
                        result["coreConnection"] = state
    return result


def enroll(installation, account, uid, gid, config, supplied):
    proof, code, certificate = supplied
    agent = config.parent
    for name, raw in (("enrollment-code", code), ("enrollment-ca.pem", certificate)):
        destination = agent / name
        reject_links(destination)
        if destination.exists():
            if read_owned(destination, uid, 65536) != raw:
                raise ValueError("E_NODE_ENROLL_INPUT")
        else:
            descriptor = os.open(
                destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
                os.fchown(stream.fileno(), uid, gid)
    run_as(
        installation,
        account,
        "--background-node-enroll",
        "--node-config",
        str(config),
        "--node-url",
        proof["url"],
        "--node-token-file",
        str(agent / "enrollment-code"),
        "--node-certificate",
        str(agent / "enrollment-ca.pem"),
        "--node-ca-sha256",
        proof["caSha256"],
    )


def configure(args) -> dict:
    target = args.target.absolute()
    require_host(target)
    if not target.exists() and not getattr(sys, "frozen", False):
        raise ValueError("E_STARTUP_FROZEN_REQUIRED")
    supplied = enrollment_input(args)
    if not target.exists() and supplied is None:
        raise ValueError("E_NODE_ENROLL_INPUT")
    if args.node_service not in {"install", "repair"} and supplied is not None:
        raise ValueError("E_NODE_ARGUMENT")
    with installation_lock(target):
        if not target.exists():
            if args.node_service != "install":
                raise ValueError("E_STATE")
            architecture = {"x86_64": "linux/amd64", "aarch64": "linux/arm64"}.get(
                platform.machine()
            )
            if architecture is None:
                raise ValueError("E_AGENT_PLATFORM")
            manifest = {"release": args.installer_version, "architecture": architecture}
            raw = worker_bytes(
                SimpleNamespace(configuration={"architecture": architecture}), None
            )
            installation = NodeInstallation(
                target,
                manifest,
                hashlib.sha256(raw).hexdigest(),
                platform.node(),
                "outbound-only",
            )
            installation.state.update(
                backend=BACKEND,
                nodeMachine=machine_binding(installation.state["installationId"]),
            )
            installation.save()
        else:
            installation = load(target)
        previous_enrollment = installation.state.get("nodeEnrollment")
        if supplied is not None:
            if previous_enrollment is not None and previous_enrollment != supplied[0]:
                raise ValueError("E_NODE_ENROLL_INPUT")
            if previous_enrollment is None and (target / "agent/agent.json").exists():
                raise ValueError("E_NODE_IDENTITY_EXISTS")
            installation.state["nodeEnrollment"] = supplied[0]
            installation.save()
        uid, gid, account = identity(
            installation, create=args.node_service == "install"
        )
        if args.node_service == "status":
            return service_state(installation)
        os.chown(target, 0, gid)
        os.chmod(target, 0o750)
        if args.node_service in {"disable", "remove"}:
            unit = owned_unit(installation)
            if unit.exists():
                systemctl("disable", "--now", unit.name)
                if args.node_service == "remove":
                    unit.unlink()
                    systemctl("daemon-reload")
            installation.state["stage"] = "service-" + args.node_service
            installation.save()
            return service_state(installation)
        previous = installation.state.get("nodeWorker")
        if previous is None:
            raw = worker_bytes(installation, None)
            if (
                hashlib.sha256(raw).hexdigest()
                != installation.configuration["manifestSha256"]
            ):
                raise ValueError("E_NODE_SERVICE_WORKER")
            name = "node-worker-" + hashlib.sha256(raw).hexdigest()[:32]
            installation.write(name, raw)
            installation.state["nodeWorker"] = name
            installation.save()
        worker = target / installation.state["nodeWorker"]
        os.chown(worker, 0, gid)
        os.chmod(worker, 0o750)
        agent = target / "agent"
        reject_links(agent)
        if not agent.exists():
            installation.state["nodeAgentDirectoryPending"] = True
            installation.save()
            agent.mkdir(mode=0o700)
        if (
            installation.state.get("nodeAgentDirectoryPending") is True
            and agent.stat().st_uid == 0
            and not any(agent.iterdir())
        ):
            os.chown(agent, uid, gid)
        if agent.stat().st_uid != uid or agent.stat().st_mode & 0o077:
            raise ValueError("E_NODE_SERVICE_IDENTITY")
        if installation.state.pop("nodeAgentDirectoryPending", None) is not None:
            installation.save()
        config = agent / "agent.json"
        reject_links(config)
        if not config.exists():
            if supplied is None:
                if not config.with_name(config.name + ".enrollment.json").is_file():
                    raise ValueError("E_NODE_ENROLL_INPUT")
                run_as(
                    installation,
                    account,
                    "--background-node-enroll",
                    "--node-config",
                    str(config),
                )
            else:
                enroll(installation, account, uid, gid, config, supplied)
            (agent / "enrollment-code").unlink(missing_ok=True)
        text = definition(installation, worker.name, account)
        digest = hashlib.sha256(text.encode()).hexdigest()
        unit = owned_unit(installation)
        if installation.state.get("nodeUnitSha256") not in {None, digest}:
            raise ValueError("E_NODE_SERVICE_UNIT")
        installation.state.update(nodeUnitSha256=digest, stage="service-registering")
        installation.save()
        if not unit.exists():
            publish_unit(unit.parent, unit.name, text)
        systemctl("daemon-reload")
        actual = dict(
            line.split("=", 1)
            for line in systemctl(
                "show",
                unit.name,
                "--property=LoadState,FragmentPath,DropInPaths,ActiveState",
            ).splitlines()
            if "=" in line
        )
        if (
            actual.get("LoadState") != "loaded"
            or actual.get("FragmentPath") != str(unit)
            or actual.get("DropInPaths")
        ):
            raise ValueError("E_NODE_SERVICE_UNIT")
        # A newly published unit need not be loaded before the first show/start.
        # reset-failed on an unloaded unit is an error, not an idempotent no-op.
        if actual.get("ActiveState") == "failed":
            systemctl("reset-failed", unit.name)
        systemctl("enable", "--now", unit.name)
        installation.state["stage"] = "service-registered"
        installation.save()
        return service_state(installation)


def guided(args, messages) -> int:
    from host import inventory

    print(messages["nodeServiceReview"])
    observed = inventory(args.target)
    # The general probe also describes the central Compose deployment. Its
    # Docker boot prerequisites do not apply to the standalone node service.
    for key in ("bootMode", "candidateProvisioning"):
        observed.pop(key, None)
    observed.update(installerProfile=BACKEND, requiredServiceManager="systemd")
    print(json.dumps(observed, ensure_ascii=True))
    print(
        json.dumps(
            {
                "target": str(args.target),
                "operation": args.node_service,
                "preserveIdentityAndData": True,
                "hardwareAccess": "network-only",
            }
        )
    )
    if args.node_certificate is not None:
        reject_links(args.node_certificate)
        with args.node_certificate.open("rb") as stream:
            certificate = stream.read(65537)
        if len(certificate) > 65536:
            raise ValueError("E_NODE_ENROLL_INPUT")
        print(
            json.dumps(
                {
                    "coreUrl": args.node_url,
                    "certificateSha256": hashlib.sha256(certificate).hexdigest(),
                }
            )
        )
        args.node_ca_sha256 = hashlib.sha256(certificate).hexdigest()
    if (
        args.node_service != "status"
        and input("[SERVICE/CANCEL]: ").strip() != "SERVICE"
    ):
        return 0
    print(json.dumps(configure(args)))
    return 0
