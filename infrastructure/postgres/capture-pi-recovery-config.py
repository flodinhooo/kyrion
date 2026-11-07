"""Read/capture installed Pi configuration; never applies configuration or restarts."""

import argparse
import datetime
import hashlib
import json
import os
import socket
import stat
import uuid
from pathlib import Path

PLATFORM = Path("/etc/kyrion/platform")
DESTINATION = Path("/var/backups/kyrion/local-v46-additions")


def sources(platform: Path) -> list[Path]:
    required = [
        platform / name
        for name in (
            "compose.yml",
            "platform.env",
            "Caddyfile",
            "tls/server.crt",
            "tls/server.key",
        )
    ]
    if platform.resolve() != platform or any(p.is_symlink() for p in platform.parents):
        raise ValueError("Platform path is redirected")
    tls = platform / "tls"
    if tls.is_symlink() or not tls.is_dir():
        raise ValueError("Unsafe TLS directory")
    if any(not stat.S_ISREG(path.lstat().st_mode) for path in required):
        raise ValueError("Required configuration must be regular files")
    candidates = sorted(set(required + list(tls.rglob("*"))))
    files = []
    for path in candidates:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("Symlinks are not accepted")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("Only regular configuration files are accepted")
        files.append(path)
    return files


def read_file(path: Path) -> tuple[bytes, dict]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Source is not a regular file")
        data = stream.read()
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if identity(before) != identity(after) or len(data) != after.st_size:
        raise ValueError("Source changed while reading")
    return data, {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "uid": after.st_uid,
        "gid": after.st_gid,
        "mode": oct(stat.S_IMODE(after.st_mode)),
    }


def capture(platform: Path, destination: Path) -> Path:
    paths = sources(platform)
    initial = {p: read_file(p) for p in paths}
    for parent in [destination, *destination.parents]:
        if parent.is_symlink():
            raise ValueError("Recovery destination is redirected")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (
        destination.stat().st_uid != os.geteuid()
        or stat.S_IMODE(destination.stat().st_mode) != 0o700
    ):
        raise ValueError("Recovery destination must be private and owned by caller")
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = destination / (timestamp + "-" + uuid.uuid4().hex[:8])
    target.mkdir(mode=0o700)
    (target / "INCOMPLETE").write_text("Capture has not passed stability checks\n")
    records = {}
    for path, (data, metadata) in initial.items():
        relative = path.relative_to(platform)
        saved = target / "files" / relative
        saved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with saved.open("xb") as stream:
            os.chmod(saved, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        records[str(relative)] = {"original_path": str(path), **metadata}
    if sources(platform) != paths:
        raise ValueError("Source inventory changed during capture")
    for path, (_, metadata) in initial.items():
        if read_file(path)[1] != metadata:
            raise ValueError("Source changed during capture; incomplete set retained")
    manifest = {
        "format": "kyrion-pi-platform-configuration-addition",
        "captured_at": timestamp,
        "files": records,
        "database_snapshot_reference": "database-backups-v46-20261107T175611Z",
        "consistency": "Stable configuration capture, not simultaneous DB/files quiescence",
        "applied_to_live": False,
    }
    with (target / "manifest.json").open("x") as stream:
        os.chmod(target / "manifest.json", 0o600)
        json.dump(manifest, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    for directory in sorted(
        [target, *(p for p in target.rglob("*") if p.is_dir())],
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    (target / "INCOMPLETE").unlink()
    fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    except OSError:
        (target / "INCOMPLETE").write_text("Directory durability check failed\n")
        raise
    finally:
        os.close(fd)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "capture"])
    args = parser.parse_args()
    if os.geteuid() != 0 or socket.gethostname() != "kyrion-node":
        raise SystemExit(
            "Requires interactive sudo on kyrion-node; no passwords accepted"
        )
    os.umask(0o077)
    if args.action == "check":
        for path in sources(PLATFORM):
            read_file(path)
        print("CONFIG_READ_CHECK_PASSED; no files captured or live settings changed")
    else:
        print("CONFIG_CAPTURED", capture(PLATFORM, DESTINATION))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(
            "REFUSED: " + type(error).__name__ + "; no source settings changed"
        ) from None
