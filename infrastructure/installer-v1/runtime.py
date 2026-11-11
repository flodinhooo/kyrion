"""Fixed operations for reviewed fresh installs. No account or integration store."""

from __future__ import annotations

import contextlib
import hashlib
import ipaddress
import json
import os
import re
import secrets
import ssl
import subprocess
import tarfile
import time
import urllib.request
import uuid
from pathlib import Path

from bundle import authenticate, sha256
from host import inventory, reject_links, runtime_checks

ROOT = Path(__file__).resolve().parent
HOSTNAME = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)


def execute(args: list[str], timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("E_RUNTIME: operation unavailable or timed out") from error
    if result.returncode:
        # Raw child output can include credentials or environment: never print it.
        raise ValueError("E_RUNTIME: operation failed: " + args[0])
    return result.stdout


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(8))
    try:
        with os.fdopen(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def installation_lock(target: Path):
    lock_path = target.parent / ("." + target.name + ".installer.lock")
    reject_links(lock_path)
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        # OPEN_ALWAYS never truncates an existing file; share mode zero excludes
        # another process and null SECURITY_ATTRIBUTES prevents inheritance.
        handle = create(
            str(lock_path.absolute()), 0xC0000000, 0, None, 4, 0x00200000, None
        )
        if handle == ctypes.c_void_p(-1).value:
            failure = ctypes.get_last_error()
            if failure in {32, 33}:
                raise ValueError("E_LOCKED: another installer owns the target")
            raise OSError("E_LOCK: cannot establish exclusive target ownership")
        try:
            reject_links(lock_path)
            yield
        finally:
            if not close(handle):
                raise OSError("E_LOCK_RELEASE")
        return
    import fcntl

    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("E_LOCKED: another installer owns the target") from None
        yield
    finally:
        os.close(descriptor)


def validate_inputs(target: Path, hostname: str, address: str) -> None:
    if (
        not target.is_absolute()
        or target == target.parent
        or not re.fullmatch(r"/[A-Za-z0-9/_-]+", str(target))
    ):
        raise ValueError(
            "E_TARGET: absolute dedicated path with simple characters required"
        )
    if not target.parent.is_dir():
        raise ValueError("E_TARGET: parent directory must exist")
    reject_links(target)
    if not HOSTNAME.fullmatch(hostname):
        raise ValueError("E_HOSTNAME: valid lowercase local DNS hostname required")
    try:
        ip = ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError:
        raise ValueError("E_ADDRESS: private IPv4 address required") from None
    if not any(
        ip in ipaddress.IPv4Network(net)
        for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    ):
        raise ValueError("E_ADDRESS: private LAN address required")


def image_plan(manifest: dict) -> dict[str, str]:
    arch = manifest["architecture"].split("/")[1]
    version = manifest["release"]
    expected = {
        f"kyrion-core-{arch}.tar": f"kyrion/core:{version}",
        f"kyrion-web-{arch}.tar": f"kyrion/web:{version}",
        f"postgres-{arch}.tar": "postgres:17.6-alpine",
        f"caddy-{arch}.tar": "caddy:2.10.2-alpine",
    }
    if {item["name"] for item in manifest["artifacts"]} != set(expected):
        raise ValueError(
            "E_ARTIFACTS: exactly the four platform image archives are required"
        )
    return expected


def image_identity(archive: Path, tag: str) -> str:
    """Read only bounded Docker metadata; never extract an archive to the host."""
    import hashlib

    try:
        with tarfile.open(archive) as stream:
            metadata = stream.getmember("manifest.json")
            if not metadata.isfile() or metadata.size > 1024 * 1024:
                raise ValueError()
            entries = json.load(stream.extractfile(metadata))
            if (
                not isinstance(entries, list)
                or len(entries) != 1
                or entries[0].get("RepoTags") != [tag]
            ):
                raise ValueError()
            config = stream.getmember(entries[0]["Config"])
            if not config.isfile() or config.size > 1024 * 1024:
                raise ValueError()
            return (
                "sha256:"
                + hashlib.sha256(stream.extractfile(config).read()).hexdigest()
            )
    except (OSError, tarfile.TarError, ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("E_IMAGE: invalid image metadata or unexpected tag") from None


class Installation:
    def __init__(
        self,
        target: Path,
        manifest: dict,
        manifest_digest: str,
        hostname: str,
        address: str,
        verify: bool = True,
    ):
        self.target = target
        self.path = target / "install-state.json"
        self.configuration = {
            "hostname": hostname,
            "address": address,
            "release": manifest["release"],
            "manifestSha256": manifest_digest,
            "architecture": manifest["architecture"],
        }
        if target.exists():
            if (
                not self.path.is_file()
                or self.path.is_symlink()
                or self.path.stat().st_size > 1024 * 1024
            ):
                raise ValueError("E_EXISTING_STATE: unowned or incomplete installation")
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if os.name == "posix" and (
                self.path.stat().st_mode & 0o077
                or self.path.stat().st_uid != os.geteuid()
            ):
                raise ValueError(
                    "E_STATE: installation journal permissions or owner are unsafe"
                )
            if (
                self.state.get("formatVersion") != 1
                or self.state.get("configuration") != self.configuration
                or not isinstance(self.state.get("files"), dict)
            ):
                raise ValueError(
                    "E_RESUME: release or configuration differs from saved installation"
                )
            if self.state.get("rootPath") != str(target.resolve()):
                raise ValueError(
                    "E_INSTALLATION_LOCATION: copied or legacy state requires explicit migration"
                )
            if verify:
                self.verify_files()
        else:
            target.mkdir(mode=0o700)
            self.state = {
                "formatVersion": 1,
                "installationId": str(uuid.uuid4()),
                "rootPath": str(target.resolve()),
                "configuration": self.configuration,
                "stage": "reviewed",
                "files": {},
                "lastError": None,
                "ownerSetup": "not-verified",
                "backup": "not-configured",
                "updates": "not-configured",
            }
            self.save()

    def save(self) -> None:
        atomic_json(self.path, self.state)

    def verify_files(self) -> None:
        for relative, digest in self.state["files"].items():
            path = self.target / relative
            if path.resolve().is_relative_to(self.target.resolve()) is False:
                raise ValueError("E_STATE: invalid managed path")
            reject_links(path)
            if not path.is_file() or sha256(path) != digest:
                raise ValueError(
                    "E_CHANGED: managed file changed; automatic repair refused"
                )
            if os.name == "posix" and path.stat().st_mode & 0o077:
                raise ValueError("E_CHANGED: managed file permissions are unsafe")

    def write(self, relative: str, value: str | bytes, uid: int | None = None) -> None:
        path = self.target / relative
        if not path.resolve().is_relative_to(self.target.resolve()):
            raise ValueError("E_STATE: invalid managed path")
        reject_links(path)
        self.verify_files()
        if relative in self.state["files"]:
            return
        pending = self.state.get("pendingWrite")
        if pending is not None:
            if not isinstance(pending, dict) or pending.get("path") != relative:
                raise ValueError(
                    "E_INCOMPLETE: a different pending write needs recovery"
                )
            if path.is_file():
                if sha256(path) != pending.get("sha256"):
                    raise ValueError(
                        "E_CHANGED: pending file differs from recorded intent"
                    )
                if os.name == "posix" and (
                    path.stat().st_mode & 0o077
                    or path.stat().st_uid != pending.get("uid")
                ):
                    raise ValueError(
                        "E_CHANGED: pending file ownership or permissions differ"
                    )
                self.state["files"][relative] = pending["sha256"]
                del self.state["pendingWrite"]
                self.save()
                return
            # No target file exists: the previous value was never published or
            # consumed. A fresh random value is safe; an existing key is never rotated.
            del self.state["pendingWrite"]
        if path.exists() or path.is_symlink():
            raise ValueError(
                "E_INCOMPLETE: uncheckpointed file preserved for inspection"
            )
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = value.encode("utf-8") if isinstance(value, str) else value
        self.state["pendingWrite"] = {
            "path": relative,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "uid": uid
            if uid is not None
            else (os.geteuid() if os.name == "posix" else None),
        }
        self.save()
        with os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as stream:
            stream.write(payload)
            if uid is not None:
                os.chown(path, uid, uid)
            stream.flush()
            os.fsync(stream.fileno())
        self.state["files"][relative] = sha256(path)
        del self.state["pendingWrite"]
        self.save()

    def configure(self) -> None:
        for name in (
            "bootstrap.secret",
            "credential.key",
            "audit-integrity.key",
            "postgres-password",
        ):
            value = (
                secrets.token_bytes(32)
                if name.endswith(".key")
                else secrets.token_urlsafe(32) + "\n"
            )
            self.write("secrets/" + name, value, uid=10001)
        self.write(
            "compose.yml", (ROOT / "templates/compose.yml").read_text(encoding="utf-8")
        )
        config = self.configuration
        self.write(
            ".env",
            "\n".join(
                [
                    "KYRION_RELEASE=" + config["release"],
                    "KYRION_HOSTNAME=" + config["hostname"],
                    "KYRION_BIND_ADDRESS=" + config["address"],
                    "KYRION_DATA_DIR=" + str(self.target / "data"),
                    "KYRION_SECRETS_DIR=" + str(self.target / "secrets"),
                    "",
                ]
            ),
        )
        self.write(
            "data/Caddyfile",
            (ROOT / "templates/Caddyfile")
            .read_text(encoding="utf-8")
            .replace("__KYRION_HOSTNAME__", config["hostname"]),
        )
        knowledge = self.target / "data/knowledge"
        reject_links(knowledge)
        if not knowledge.exists():
            knowledge.mkdir(mode=0o700)
            os.chown(knowledge, 10001, 10001)
        tls = self.target / "data/tls"
        reject_links(tls)
        tls.mkdir(mode=0o700, exist_ok=True)
        if "data/tls/key.pem" not in self.state["files"]:
            if any(tls.iterdir()):
                raise ValueError("E_INCOMPLETE: existing TLS material preserved")
            execute(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:3072",
                    "-sha256",
                    "-nodes",
                    "-days",
                    "365",
                    "-subj",
                    "/CN=" + config["hostname"],
                    "-addext",
                    "basicConstraints=critical,CA:FALSE",
                    "-addext",
                    "subjectAltName=DNS:"
                    + config["hostname"]
                    + ",IP:"
                    + config["address"],
                    "-keyout",
                    str(tls / "key.pem"),
                    "-out",
                    str(tls / "cert.pem"),
                ]
            )
            for filename in ("key.pem", "cert.pem"):
                os.chmod(tls / filename, 0o600)
                self.state["files"]["data/tls/" + filename] = sha256(tls / filename)
            self.save()
        self.state["stage"] = "configured"
        self.save()

    def compose(self, *args: str, timeout: int = 120) -> str:
        return execute(
            [
                "docker",
                "compose",
                "--project-name",
                "kyrion-" + self.state["installationId"],
                "--env-file",
                str(self.target / ".env"),
                "-f",
                str(self.target / "compose.yml"),
                *args,
            ],
            timeout,
        )

    def start(self) -> None:
        self.verify_files()
        self.compose("config", "--quiet")
        self.state["stage"] = "starting"
        self.save()
        self.compose(
            "up",
            "-d",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "180",
            timeout=210,
        )
        self.check_health()

    def check_health(self) -> None:
        # Caddy only routes Web. Use Core's container health, not a nonexistent
        # public /actuator/health route. Validate JSON, not just HTTP 200.
        response = json.loads(
            self.compose(
                "exec",
                "-T",
                "core",
                "curl",
                "--fail",
                "--silent",
                "--max-time",
                "10",
                "http://127.0.0.1:8080/actuator/health",
            )
        )
        if not isinstance(response, dict) or response.get("status") != "UP":
            raise ValueError("E_CORE: Core is not ready")
        config = self.configuration
        context = ssl.create_default_context(
            cafile=str(self.target / "data/tls/cert.pem")
        )
        context.check_hostname = True
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=context),
        )
        with opener.open(
            "https://" + config["hostname"] + "/login", timeout=15
        ) as response:
            if (
                response.status != 200
                or b"<html" not in response.read(1024 * 1024).lower()
            ):
                raise ValueError("E_WEB: local login is not ready")
        self.state["stage"] = "services-healthy"
        self.state["lastError"] = None
        self.state["lastHealthCheck"] = int(time.time())
        self.save()


def provision(
    target: Path,
    bundle: Path,
    public_key: Path,
    hostname: str,
    address: str,
    expected_digest: str,
) -> dict:
    validate_inputs(target, hostname, address)
    observed = inventory(target)
    if not observed["candidateProvisioning"] or os.geteuid() != 0:
        raise ValueError("E_PLATFORM: supported candidate Linux host and root required")
    if observed["ramBytes"] is None or observed["ramBytes"] < 4 * 1024**3:
        raise ValueError(
            "E_MEMORY: 4 GiB RAM required; unknown capacity cannot be approved"
        )
    if observed["freeBytes"] is None or observed["freeBytes"] < 12 * 1024**3:
        raise ValueError("E_DISK: 12 GiB free required")
    with installation_lock(target):
        manifest = authenticate(bundle, public_key)
        digest = sha256(bundle / "manifest.json")
        if (
            digest != expected_digest
            or manifest["architecture"] != "linux/" + observed["architecture"]
        ):
            raise ValueError("E_RELEASE: reviewed release or architecture differs")
        plan = image_plan(manifest)
        runtime_checks(address, hostname, fresh=not target.exists())
        if not target.exists():
            # Never adopt existing Kyrion containers, including stopped ones.
            existing = execute(
                ["docker", "ps", "-a", "--format", "{{.Image}} {{.Names}}"]
            )
            if any("kyrion" in line.lower() for line in existing.splitlines()):
                raise ValueError(
                    "E_EXISTING_STATE: existing Kyrion containers require explicit migration"
                )
        installation = Installation(target, manifest, digest, hostname, address)
        try:
            # Validate every archive's image metadata before the first Docker load.
            identities = {
                name: image_identity(bundle / name, tag) for name, tag in plan.items()
            }
            for name, tag in plan.items():
                # Recheck just before loading; never glob or silently ignore failure.
                item = next(
                    item for item in manifest["artifacts"] if item["name"] == name
                )
                if sha256(bundle / name) != item["sha256"]:
                    raise ValueError("E_DIGEST: artifact changed after review")
                execute(["docker", "load", "--input", str(bundle / name)], timeout=600)
                loaded = json.loads(execute(["docker", "image", "inspect", tag]))[0]
                if (
                    loaded.get("Id") != identities[name]
                    or loaded.get("Os") != "linux"
                    or loaded.get("Architecture") != observed["architecture"]
                ):
                    raise ValueError(
                        "E_IMAGE: loaded image identity or architecture differs"
                    )
            installation.configure()
            installation.start()
            return installation.state
        except (Exception, KeyboardInterrupt) as error:
            # Store only a bounded machine code, never raw subprocess/provider output.
            code = str(error).split(":", 1)[0]
            installation.state["lastError"] = (
                code if re.fullmatch(r"E_[A-Z_]+", code) else "E_INTERRUPTED"
            )
            installation.save()
            raise
