"""Reproducible public Windows profile assembly from pinned vendor archives.

No services, trust stores, local .env files, signing keys or publication involved.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
import urllib.request
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_identity import read_build
from bundle import VERSION, sha256, unique_object
from gpg_profile import verify_profile as verify_gpg_profile
from host import reject_links
from native_bundle import MAXIMUM_EXPANDED, safe_member

ROOT = Path(__file__).resolve().parent


def verify_service_identity(root: Path, version: str) -> None:
    reject_links(root)
    path = root / "build-source.json"
    reject_links(path)
    if not path.is_file() or path.stat().st_size > 1024**2:
        raise ValueError("E_NATIVE_SERVICE_BUILD")
    metadata = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    if (
        not isinstance(metadata, dict)
        or metadata.get("format") != "onedir"
        or metadata.get("embeddedVersion") != version
        or metadata.get("embeddedVersionVerified") is not True
        or read_build(root / "_internal", frozen=True)["version"] != version
    ):
        raise ValueError("E_NATIVE_SERVICE_BUILD")


def core_schema(core_jar: Path) -> int:
    reject_links(core_jar)
    if not core_jar.is_file() or core_jar.stat().st_size > 512 * 1024**2:
        raise ValueError("E_NATIVE_CORE_SCHEMA")
    try:
        with zipfile.ZipFile(core_jar) as archive:
            if len(archive.infolist()) > 100000:
                raise ValueError("E_NATIVE_CORE_SCHEMA")
            versions = [
                int(match[1])
                for name in archive.namelist()
                if (
                    match := re.fullmatch(
                        r"BOOT-INF/classes/db/migration/V([1-9][0-9]*)__[^/]+\.sql",
                        name,
                    )
                )
            ]
    except (OSError, zipfile.BadZipFile):
        raise ValueError("E_NATIVE_CORE_SCHEMA") from None
    if not versions or len(versions) != len(set(versions)) or max(versions) < 48:
        raise ValueError("E_NATIVE_CORE_SCHEMA")
    return max(versions)


def vendor_archives(directory: Path, fetch: bool = False) -> dict:
    lock = json.loads((ROOT / "windows-runtime-lock.json").read_text())
    directory.mkdir(parents=True, exist_ok=True)
    for source in lock["sources"]:
        path = directory / source["file"]
        reject_links(path)
        if not path.exists():
            if not fetch:
                raise ValueError("E_NATIVE_VENDOR_ARCHIVE_REQUIRED")
            temporary = directory / (source["file"] + ".part-" + uuid.uuid4().hex)
            with (
                urllib.request.urlopen(source["url"], timeout=30) as response,
                temporary.open("xb") as output,
            ):
                count = 0
                while chunk := response.read(1024**2):
                    count += len(chunk)
                    if count > source["bytes"]:
                        raise ValueError("E_NATIVE_VENDOR_SIZE")
                    output.write(chunk)
            if (
                temporary.stat().st_size != source["bytes"]
                or sha256(temporary) != source["sha256"]
            ):
                raise ValueError("E_NATIVE_VENDOR_DIGEST")
            temporary.rename(path)
        if (
            not path.is_file()
            or path.stat().st_size != source["bytes"]
            or sha256(path) != source["sha256"]
        ):
            raise ValueError("E_NATIVE_VENDOR_DIGEST")
    return {row["component"]: row for row in lock["sources"]}


def assemble(
    archives: Path,
    core_jar: Path,
    parser_jar: Path,
    web_build: Path,
    service_host: Path,
    output: Path,
    version: str,
    schema: int | None,
    gnupg_profile: Path | None = None,
) -> dict:
    if (
        not VERSION.fullmatch(version)
        or output.exists()
        or not output.parent.is_dir()
        or schema is not None
        and (type(schema) is not int or schema < 48)
    ):
        raise ValueError("E_NATIVE_PROFILE_INPUT")
    actual_schema = core_schema(core_jar)
    if schema is not None and schema != actual_schema:
        raise ValueError("E_NATIVE_PROFILE_SCHEMA")
    schema = actual_schema
    verify_service_identity(service_host, version)
    if gnupg_profile is not None:
        verify_gpg_profile(gnupg_profile)
    sources = vendor_archives(archives)
    output.mkdir()
    total = 0
    names = set()

    def write(name, data):
        nonlocal total
        safe_member(name)
        if name.casefold() in names or len(names) >= 20000:
            raise ValueError("E_NATIVE_PROFILE_DUPLICATE")
        names.add(name.casefold())
        total += len(data)
        if total > MAXIMUM_EXPANDED or len(data) > 1024**3:
            raise ValueError("E_NATIVE_PROFILE_SIZE")
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)

    def copy(name, path):
        reject_links(path)
        if not path.is_file() or path.stat().st_size > 1024**3:
            raise ValueError("E_NATIVE_PROFILE_SOURCE")
        write(name, path.read_bytes())

    legal = {}
    for component, source in sources.items():
        with zipfile.ZipFile(archives / source["file"]) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                raw = member.filename
                selected = None
                if component == "java" and raw.startswith("jdk-21.0.13+9-jre/"):
                    selected = "runtime/java/" + raw.removeprefix("jdk-21.0.13+9-jre/")
                elif component == "node" and raw == "node-v22.23.3-win-x64/node.exe":
                    selected = "runtime/node/node.exe"
                elif component == "caddy" and raw == "caddy.exe":
                    selected = "runtime/caddy/caddy.exe"
                elif component == "postgres" and (
                    raw.startswith(
                        ("pgsql/bin/", "pgsql/lib/", "pgsql/share/", "pgsql/doc/")
                    )
                    or raw
                    in {
                        "pgsql/server_license.txt",
                        "pgsql/commandlinetools_3rd_party_licenses.txt",
                    }
                ):
                    selected = "runtime/postgres/" + raw.removeprefix("pgsql/")
                if selected:
                    if (
                        stat.S_ISLNK(member.external_attr >> 16)
                        or member.file_size > 1024**3
                    ):
                        raise ValueError("E_NATIVE_VENDOR_MEMBER")
                    write(selected, archive.read(member))
            if component == "java":
                legal[component] = b"\n".join(
                    archive.read("jdk-21.0.13+9-jre/legal/java.base/" + name)
                    for name in ("LICENSE", "ASSEMBLY_EXCEPTION")
                )
            elif component == "node":
                legal[component] = archive.read("node-v22.23.3-win-x64/LICENSE")
            elif component == "caddy":
                legal[component] = archive.read("LICENSE")
            else:
                legal[component] = b"\n".join(
                    archive.read("pgsql/" + name)
                    for name in (
                        "server_license.txt",
                        "commandlinetools_3rd_party_licenses.txt",
                    )
                )
    copy("app/core/core-runtime.jar", core_jar)
    copy("app/core/knowledge-parser.jar", parser_jar)
    for prefix, source in (
        ("app/web", web_build / ".next/standalone"),
        ("app/web/.next/static", web_build / ".next/static"),
        ("app/web/public", web_build / "public"),
    ):
        reject_links(source)
        if not source.is_dir():
            raise ValueError("E_NATIVE_WEB_BUILD")
        for path in sorted(source.rglob("*")):
            reject_links(path)
            if path.is_file():
                copy(prefix + "/" + path.relative_to(source).as_posix(), path)
    reject_links(service_host)
    if not service_host.is_dir():
        raise ValueError("E_NATIVE_SERVICE_HOST")
    for path in sorted(service_host.rglob("*")):
        reject_links(path)
        if path.is_file():
            copy("runtime/installer/" + path.relative_to(service_host).as_posix(), path)
    if gnupg_profile is not None:
        for path in sorted(gnupg_profile.rglob("*")):
            if path.is_file():
                copy(
                    "runtime/installer/gnupg/"
                    + path.relative_to(gnupg_profile).as_posix(),
                    path,
                )
        verify_gpg_profile(output / "runtime/installer/gnupg")
    notice = b"Kyrion has no selected repository LICENSE. All rights reserved; no redistribution grant is implied by this development build.\n"
    for component in ("core", "web", "installer"):
        legal[component] = notice
    for component, data in legal.items():
        write("licenses/" + component + ".txt", data)
    metadata = json.loads((ROOT / "windows-runtime-components.json").read_text())
    for component in ("core", "web", "installer"):
        metadata[component] = {
            "version": version,
            "sourceUrl": "https://kyrion.ch",
            "license": "LicenseRef-Kyrion-All-Rights-Reserved",
            "licenseUrl": None,
        }
    return {
        "release": version,
        "components": metadata,
        "compatibility": {"api": 1, "schema": schema, "postgresMajor": 17},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download only the reviewed pinned vendor archives",
    )
    parser.add_argument("--core-jar", type=Path)
    parser.add_argument("--parser-jar", type=Path)
    parser.add_argument("--web-build", type=Path)
    parser.add_argument("--service-host", type=Path)
    parser.add_argument("--gnupg-profile", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--version")
    parser.add_argument(
        "--schema",
        type=int,
        help="Optional assertion; schema is derived from the actual Core JAR",
    )
    args = parser.parse_args()
    vendor_archives(args.archives, args.fetch)
    if args.output:
        if None in (
            args.core_jar,
            args.parser_jar,
            args.web_build,
            args.service_host,
            args.version,
        ):
            raise SystemExit("E_NATIVE_PROFILE_ARGUMENTS")
        metadata = assemble(
            args.archives,
            args.core_jar,
            args.parser_jar,
            args.web_build,
            args.service_host,
            args.output,
            args.version,
            args.schema,
            args.gnupg_profile,
        )
        (args.output.parent / (args.output.name + "-metadata.json")).write_text(
            json.dumps(metadata, indent=2) + "\n"
        )
        print(
            json.dumps(
                {
                    "profile": str(args.output),
                    "signed": False,
                    "platformInstallationAccepted": False,
                }
            )
        )
