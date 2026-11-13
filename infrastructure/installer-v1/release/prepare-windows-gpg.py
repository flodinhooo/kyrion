"""Prepare signed-vendor portable GnuPG data; never execute its installer.

GnuPG and 7-Zip are build tools. Customer execution uses only the resulting
manifest-hashed AMD64 support payload, not a PATH tool or system installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from bundle import sha256, unique_object
from host import reject_links
from native_bundle import pe_amd64, safe_member
from release_policy import NoRedirect

MAX_EXPANDED = 64 * 1024**2


def source_files(directory: Path, lock: dict, fetch: bool = False) -> dict[str, Path]:
    reject_links(directory)
    directory.mkdir(parents=True, exist_ok=True)
    selected = {}
    for kind, source in lock["sources"].items():
        name = source["file"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", name):
            raise ValueError("E_GPG_VENDOR_LOCK")
        path = directory / name
        reject_links(path)
        if not path.exists():
            if not fetch:
                raise ValueError("E_GPG_VENDOR_REQUIRED")
            if not source["url"].startswith(
                ("https://gnupg.org/", "https://www.gnupg.org/")
            ):
                raise ValueError("E_GPG_VENDOR_LOCK")
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(source["url"], timeout=60) as response:
                raw = response.read(source["bytes"] + 1)
            if (
                len(raw) != source["bytes"]
                or hashlib.sha256(raw).hexdigest() != source["sha256"]
            ):
                raise ValueError("E_GPG_VENDOR_INTEGRITY")
            with path.open("xb") as stream:
                stream.write(raw)
        if (
            not path.is_file()
            or path.stat().st_size != source["bytes"]
            or sha256(path) != source["sha256"]
        ):
            raise ValueError("E_GPG_VENDOR_INTEGRITY")
        selected[kind] = path
    return selected


def verify_vendor(
    files: dict[str, Path], fingerprint: str, gpg: Path, scratch: Path
) -> None:
    keyring = scratch / "keyring"
    keyring.mkdir(mode=0o700)
    argument = str(keyring)
    if os.name == "nt" and gpg.with_name("msys-2.0.dll").is_file():
        argument = "/" + keyring.drive[0].lower() + keyring.as_posix()[2:]
    base = [
        str(gpg),
        "--no-options",
        "--homedir",
        argument,
        "--batch",
        "--no-auto-key-retrieve",
        "--no-autostart",
    ]
    subprocess.run(
        base + ["--import", str(files["keys"])],
        capture_output=True,
        check=True,
        timeout=30,
    )
    for archive, signature in (
        ("archive", "signature"),
        ("sourceArchive", "sourceSignature"),
    ):
        verify_signature(base, files[archive], files[signature], fingerprint)


def verify_signature(
    base: list[str], archive: Path, signature: Path, fingerprint: str
) -> None:
    verified = subprocess.run(
        base
        + [
            "--status-fd",
            "1",
            "--verify",
            str(signature),
            str(archive),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    signatures = [
        line.split()
        for line in verified.stdout.decode("ascii", errors="replace").splitlines()
        if line.startswith("[GNUPG:] VALIDSIG ")
    ]
    if len(signatures) != 1 or fingerprint not in {signatures[0][2], signatures[0][-1]}:
        raise ValueError("E_GPG_VENDOR_SIGNATURE")


def retain_sources(extracted: Path, sealed: dict[str, Path], lock: dict) -> None:
    """Retain corresponding source and original notices without extracting code."""
    target = extracted / "share/kyrion-source"
    target.mkdir()
    for kind in ("sourceArchive", "sourceSignature", "keys"):
        shutil.copyfile(sealed[kind], target / sealed[kind].name)
    licenses = target / "licenses"
    licenses.mkdir()
    prefix = "gnupg-w32-" + lock["version"]
    selected = ["COPYING"]
    for component, names in {
        "libksba": ("COPYING",),
        "libassuan": ("COPYING", "COPYING.LIB"),
        "npth": ("COPYING.LIB",),
        "ntbtls": ("COPYING",),
        "libgcrypt": ("COPYING", "COPYING.LIB"),
        "libgpg-error": ("COPYING", "COPYING.LIB"),
        "pinentry": ("COPYING",),
    }.items():
        selected.extend("PLAY/src/" + component + "/" + name for name in names)
    with tarfile.open(sealed["sourceArchive"], "r:xz") as archive:
        members = archive.getmembers()
        for name in selected:
            matches = [item for item in members if item.name == prefix + "/" + name]
            if (
                len(matches) != 1
                or not matches[0].isfile()
                or not 0 < matches[0].size <= 65536
            ):
                raise ValueError("E_GPG_SOURCE_LICENSE")
            stream = archive.extractfile(matches[0])
            if stream is None:
                raise ValueError("E_GPG_SOURCE_LICENSE")
            with stream:
                (licenses / name.replace("/", "--")).write_bytes(stream.read(65537))


def review_listing(raw: bytes) -> None:
    if len(raw) > 1024**2:
        raise ValueError("E_GPG_PROFILE_LISTING")
    active = False
    names = set()
    for line in raw.decode("utf-8", errors="strict").splitlines():
        if line == "----------":
            active = True
        elif active and line.startswith("Path = "):
            name = line.removeprefix("Path = ").replace("\\", "/")
            # NSIS embeds installer-only plugin paths (including upstream
            # build paths). They are excluded by the positive extraction list.
            if (
                not name.casefold().startswith(("bin/", "share/"))
                and name.casefold() != "readme.txt"
            ):
                continue
            safe_member("runtime/installer/gnupg/" + name)
            if name.casefold() in names:
                raise ValueError("E_GPG_PROFILE_LISTING")
            names.add(name.casefold())
        elif active and line.startswith(("Symbolic Link = ", "Hard Link = ")):
            raise ValueError("E_GPG_PROFILE_LISTING")
    if not names or len(names) > 1000:
        raise ValueError("E_GPG_PROFILE_LISTING")


def prepare(
    sources: Path, output: Path, gpg: Path, extractor: Path, fetch: bool = False
) -> dict:
    reject_links(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError("E_GPG_PROFILE_TARGET")
    gpg, extractor = gpg.resolve(), extractor.resolve()
    if not gpg.is_file() or not extractor.is_file():
        raise ValueError("E_GPG_BUILD_TOOL")
    lock = json.loads(
        (ROOT / "gnupg-windows-lock.json").read_bytes(), object_pairs_hook=unique_object
    )
    sources = sources.resolve()
    checked = source_files(sources, lock, fetch)
    with tempfile.TemporaryDirectory(
        prefix="kyrion-gpg-build-", dir=output.parent
    ) as directory:
        scratch = Path(directory).resolve()
        sealed = {}
        for kind, source in checked.items():
            path = scratch / source.name
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != lock["sources"][kind]["sha256"]:
                raise ValueError("E_GPG_VENDOR_CHANGED")
            path.write_bytes(raw)
            sealed[kind] = path
        verify_vendor(sealed, lock["primaryFingerprint"], gpg, scratch)
        listing = subprocess.run(
            [str(extractor), "l", "-slt", "-sccUTF-8", str(sealed["archive"])],
            capture_output=True,
            check=True,
            timeout=30,
        )
        review_listing(listing.stdout)
        extracted = scratch / "portable"
        subprocess.run(
            [
                str(extractor),
                "x",
                "-y",
                "-o" + str(extracted),
                str(sealed["archive"]),
                "bin/*",
                "share/*",
                "README.txt",
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
        if not extracted.is_dir():
            raise ValueError("E_GPG_PROFILE_INCOMPLETE")
        retain_sources(extracted, sealed, lock)
        records = {}
        total = 0
        for path in sorted(extracted.rglob("*")):
            reject_links(path)
            if path.is_dir():
                continue
            name = path.relative_to(extracted).as_posix()
            safe_member("runtime/installer/gnupg/" + name)
            if not name.startswith(("bin/", "share/")) and name != "README.txt":
                raise ValueError("E_GPG_PROFILE_PATH")
            total += path.stat().st_size
            if not path.is_file() or total > MAX_EXPANDED or len(records) >= 1000:
                raise ValueError("E_GPG_PROFILE_SIZE")
            if path.suffix.lower() in {".exe", ".dll"}:
                with path.open("rb") as stream:
                    if not pe_amd64(stream):
                        raise ValueError("E_GPG_PROFILE_ARCHITECTURE")
            records[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        if (
            not {"bin/gpg.exe", "bin/gpgconf.exe", "bin/gpg-agent.exe", "README.txt"}
            <= records.keys()
        ):
            raise ValueError("E_GPG_PROFILE_INCOMPLETE")
        marker = extracted / "bin/gpgconf.ctl"
        with marker.open("xb"):
            pass
        records["bin/gpgconf.ctl"] = {"bytes": 0, "sha256": sha256(marker)}
        metadata = {
            "formatVersion": 1,
            "kind": "kyrion-portable-gnupg",
            "version": lock["version"],
            "sourceUrl": lock["sources"]["archive"]["url"],
            "sourceSha256": lock["sources"]["archive"]["sha256"],
            "verifiedPrimaryFingerprint": lock["primaryFingerprint"],
            "vendorSignatureVerified": True,
            "correspondingSourceSignatureVerified": True,
            "files": records,
            "productionReleaseAccepted": False,
        }
        (extracted / "vendor.json").write_text(
            json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copytree(extracted, output)
    return {
        "version": lock["version"],
        "vendorSignatureVerified": True,
        "amd64": True,
        "files": len(records),
        "installerExecuted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gpg", type=Path, required=True)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.sources, args.output, args.gpg, args.extractor, args.fetch)
        )
    )
