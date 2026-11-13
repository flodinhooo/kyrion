"""Build a native standalone installer on the actual target platform."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(output: Path, version: str, channel: Path | None = None) -> Path:
    sys.path.insert(0, str(ROOT))
    from bundle import VERSION
    from package import FILES
    from release_channel import stamp
    from source_snapshot import stage_sources

    if not VERSION.fullmatch(version) or "latest" in version.lower():
        raise ValueError("E_RELEASE")
    machine = {
        "amd64": "amd64",
        "x86_64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(platform.machine().lower())
    system = {"Windows": "windows", "Linux": "linux"}.get(platform.system())
    if not system or not machine or (system == "windows" and machine != "amd64"):
        raise ValueError("E_PLATFORM")
    name = f"kyrion-installer-{version}-{system}-{machine}"
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / (name + (".exe" if system == "windows" else ".tar.gz"))
    if artifact.exists():
        raise ValueError("E_EXISTING_STATE")
    with tempfile.TemporaryDirectory(prefix="kyrion-freeze-") as directory:
        temporary = Path(directory)
        source = temporary / "source"
        source_snapshot = stage_sources(ROOT, source, (*FILES, "package.py"))
        build_identity = stamp(source, version, channel)
        arguments = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--noupx",
            "--onefile",
            "--name",
            name,
            "--distpath",
            str(temporary / "dist"),
            "--workpath",
            str(temporary / "work"),
            "--specpath",
            str(temporary),
            "--paths",
            str(source),
        ]
        # Explicit data allowlist. Python imports are analyzed by PyInstaller.
        for relative in (
            "installer-build.json",
            "windows-permissions.ps1",
            "windows-task-security.ps1",
            "windows-tasks.ps1",
            "locales/en.json",
            "locales/de.json",
            "model-catalog.json",
            "templates/compose.yml",
            "templates/Caddyfile",
        ):
            arguments += [
                "--add-data",
                str(source / relative) + ":" + str(Path(relative).parent),
            ]
        if channel is not None:
            arguments += ["--add-data", str(source / "installer-channel.json") + ":."]
        arguments += [str(source / "guided.py")]
        subprocess.run(
            arguments,
            env={**os.environ, "PYINSTALLER_CONFIG_DIR": str(temporary / "cache")},
            check=True,
            timeout=600,
        )
        binary = temporary / "dist" / (name + (".exe" if system == "windows" else ""))
        # A built executable must actually run without using the source entrypoint.
        probe = subprocess.run(
            [str(binary), "--probe"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        observed = json.loads(probe.stdout)
        if (
            observed.get("system") != platform.system()
            or observed.get("architecture") != machine
        ):
            raise ValueError("E_NATIVE_SMOKE")
        built_version = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        if built_version.stdout.strip() != version:
            raise ValueError("E_NATIVE_BUILD_VERSION")
        channel_probe = subprocess.run(
            [str(binary), "--channel-info"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        observed_channel = json.loads(channel_probe.stdout)
        if observed_channel.get("configured") is not (
            channel is not None
        ) or observed_channel.get("sha256") != build_identity.get(
            "releaseChannelSha256"
        ):
            raise ValueError("E_NATIVE_BUILD_CHANNEL")
        if source_snapshot != {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in source_snapshot
        }:
            raise ValueError("E_NATIVE_SOURCE_CHANGED")
        if system == "windows":
            with artifact.open("xb") as stream:
                stream.write(binary.read_bytes())
        else:
            with (
                artifact.open("xb") as stream,
                tarfile.open(fileobj=stream, mode="w:gz") as archive,
            ):
                archive.add(binary, arcname="kyrion-installer", recursive=False)
    with artifact.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    metadata = {
        "schemaVersion": 1,
        "version": version,
        "platform": f"{system}-{machine}",
        "file": artifact.name,
        "bytes": artifact.stat().st_size,
        "sha256": digest,
        "nativeSmokeTest": True,
        "platformInstallationAccepted": False,
        "signed": False,
        "sources": source_snapshot,
        "embeddedVersionVerified": True,
        "releaseChannelSha256": build_identity.get("releaseChannelSha256"),
        "embeddedChannelVerified": True,
    }
    artifact.with_suffix(artifact.suffix + ".json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata))
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--channel", type=Path)
    arguments = parser.parse_args()
    build(arguments.output, arguments.version, arguments.channel)
