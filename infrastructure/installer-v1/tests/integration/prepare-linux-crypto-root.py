"""Prepare a new owned Debian chroot; never install packages on the host.

Requires the existing marked disposable Linux developer guest. Downloads an
official Debian OCI layer over verified TLS and records the digest chain. This
is development fixture provenance, not a Kyrion signed release acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import backup_store
from package import FILES


class StopRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def response(url, *, token=None, accept=None):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), StopRedirect()
    )
    for _ in range(5):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("E_TEST_OCI_URL")
        headers = {"Accept": accept} if accept else {}
        if token and parsed.hostname == "registry-1.docker.io":
            headers["Authorization"] = "Bearer " + token
        try:
            return opener.open(urllib.request.Request(url, headers=headers), timeout=30)
        except urllib.error.HTTPError as error:
            if error.code not in {301, 302, 303, 307, 308} or not error.headers.get(
                "Location"
            ):
                raise ValueError("E_TEST_OCI_DOWNLOAD") from None
            url = urljoin(url, error.headers["Location"])
    raise ValueError("E_TEST_OCI_REDIRECT")


def main(kind: str = "crypto"):
    marker = json.loads(Path("/work/kyrion-systemd-fixture.json").read_bytes())
    if (
        os.geteuid() != 0
        or marker.get("scope") != "installer-systemd-development-fixture"
        or platform.machine() != "x86_64"
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    parent = Path("/work/crypto-clean-fixtures")
    parent.mkdir(mode=0o700, exist_ok=True)
    backup_store.secure_directory(parent)
    work = parent / uuid.uuid4().hex
    work.mkdir(mode=0o700)
    token_url = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/debian:pull"
    with response(token_url) as stream:
        token = json.loads(stream.read(65536))["token"]
    registry = "https://registry-1.docker.io/v2/library/debian/"
    accept = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json"
    with response(registry + "manifests/13-slim", token=token, accept=accept) as stream:
        index_raw = stream.read(2 * 1024**2)
    index = json.loads(index_raw)
    matches = [
        row
        for row in index["manifests"]
        if row.get("platform", {}).get("os") == "linux"
        and row["platform"].get("architecture") == "amd64"
    ]
    if len(matches) != 1:
        raise ValueError("E_TEST_OCI_PLATFORM")
    digest = matches[0]["digest"]
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise ValueError("E_TEST_OCI_DIGEST")
    with response(
        registry + "manifests/" + digest, token=token, accept=accept
    ) as stream:
        raw = stream.read(2 * 1024**2)
    if "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("E_TEST_OCI_DIGEST")
    manifest = json.loads(raw)
    if len(manifest["layers"]) != 1:
        raise ValueError("E_TEST_OCI_LAYERS")
    layer = manifest["layers"][0]
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", layer["digest"]):
        raise ValueError("E_TEST_OCI_DIGEST")
    if not 1 <= layer["size"] <= 512 * 1024**2:
        raise ValueError("E_TEST_OCI_SIZE")
    archive = work / "debian-rootfs.tar.gz"
    checksum, size = hashlib.sha256(), 0
    with (
        response(registry + "blobs/" + layer["digest"], token=token) as stream,
        archive.open("xb") as output,
    ):
        while chunk := stream.read(1024**2):
            size += len(chunk)
            if size > layer["size"]:
                raise ValueError("E_TEST_OCI_SIZE")
            checksum.update(chunk)
            output.write(chunk)
    if size != layer["size"] or "sha256:" + checksum.hexdigest() != layer["digest"]:
        raise ValueError("E_TEST_OCI_DIGEST")
    root = work / "root"
    root.mkdir(mode=0o700)
    with tarfile.open(archive) as package:
        members = package.getmembers()
        symlinks = set()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or member.isdev():
                raise ValueError("E_TEST_ROOTFS_PATH")
            if member.issym():
                symlinks.add(name)
            if member.islnk() and (
                PurePosixPath(member.linkname).is_absolute()
                or ".." in PurePosixPath(member.linkname).parts
            ):
                raise ValueError("E_TEST_ROOTFS_PATH")
        if any(
            any(parent in symlinks for parent in PurePosixPath(member.name).parents)
            for member in members
        ):
            raise ValueError("E_TEST_ROOTFS_ALIAS")
    subprocess.run(
        ["/usr/bin/tar", "--numeric-owner", "-xzf", str(archive), "-C", str(root)],
        check=True,
        timeout=90,
    )
    for name, minor in (("null", 3), ("random", 8), ("urandom", 9)):
        path = root / "dev" / name
        if not path.exists():
            os.mknod(path, stat.S_IFCHR | 0o666, os.makedev(1, minor))
    resolv = root / "etc/resolv.conf"
    resolv.unlink(missing_ok=True)
    resolv.write_bytes(Path("/etc/resolv.conf").read_bytes())
    policy = root / "usr/sbin/policy-rc.d"
    if policy.exists():
        if policy.is_symlink() or policy.stat().st_size > 4096:
            raise ValueError("E_TEST_ROOTFS_POLICY")
        text = policy.read_text()
        commands = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not text.startswith("#!/bin/sh\n") or commands != ["exit 101"]:
            raise ValueError("E_TEST_ROOTFS_POLICY")
    else:
        policy.write_text("#!/bin/sh\nexit 101\n")
        policy.chmod(0o700)
    (root / "work").mkdir(mode=0o700)
    identity = root.stat()
    private_marker = root / "etc/kyrion-crypto-package-fixture.json"
    private_marker.write_text(
        json.dumps(
            {
                "scope": "installer-crypto-package-development-fixture",
                "rootDevice": identity.st_dev,
                "rootInode": identity.st_ino,
                "purpose": kind,
            }
        )
    )
    private_marker.chmod(0o600)
    source = Path(__file__).resolve().parents[2]
    destination = root / "opt/kyrion-installer"
    for name in FILES:
        item = source / name
        if item.is_symlink() or not item.is_file() or item.stat().st_size > 1024**2:
            raise ValueError("E_TEST_PUBLIC_SOURCE")
        output = destination / name
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(item, output)
    shutil.copyfile(
        Path(__file__).with_name(
            "verify-linux-crypto-install.py"
            if kind == "crypto"
            else "verify-linux-runtime-packages.py"
        ),
        root / "opt/verify-crypto.py",
    )
    prefix = [
        "/usr/bin/unshare",
        "--mount",
        "--pid",
        "--fork",
        "--kill-child",
        "--mount-proc=" + str(root / "proc"),
        "/usr/sbin/chroot",
        str(root),
    ]
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/root",
        "LC_ALL": "C",
        "DEBIAN_FRONTEND": "noninteractive",
    }
    with (work / "private-package-output.log").open("xb") as output:
        for arguments in (
            ["/usr/bin/apt-get", "update"],
            [
                "/usr/bin/apt-get",
                "--yes",
                "--no-install-recommends",
                "install",
                "python3",
                "ca-certificates",
            ],
            ["/usr/bin/python3", "/opt/verify-crypto.py"],
        ):
            result = subprocess.run(
                prefix + arguments,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=900,
                check=False,
            )
            if result.returncode:
                raise ValueError("E_TEST_CHROOT_PACKAGE_OPERATION")
    report = json.loads((root / "work/report.json").read_bytes())
    report["officialDebianOciManifest"] = digest
    report["officialDebianRootfsLayer"] = layer["digest"]
    (work / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"report": str(work / "report.json"), **report}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("crypto", "runtime"), default="crypto")
    main(parser.parse_args().kind)
