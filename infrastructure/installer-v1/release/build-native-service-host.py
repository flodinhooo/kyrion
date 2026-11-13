"""Build the signed-runtime component's one-directory Windows SCM host.

Only public allowlisted data is copied; no services are registered by the build.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(
    output: Path, version: str | None = None, channel: Path | None = None
) -> dict:
    if platform.system() != "Windows" or platform.machine().lower() not in {
        "amd64",
        "x86_64",
    }:
        raise ValueError("E_SERVICE_HOST_BUILD_PLATFORM")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("E_SERVICE_HOST_BUILD_TARGET")
    sys.path.insert(0, str(ROOT))
    from build_identity import DEVELOPMENT_VERSION
    from bundle import VERSION, sha256
    from package import FILES
    from release_channel import stamp
    from source_snapshot import stage_sources

    version = version if version is not None else DEVELOPMENT_VERSION
    if not VERSION.fullmatch(version) or "latest" in version.lower():
        raise ValueError("E_RELEASE")

    with tempfile.TemporaryDirectory(prefix="kyrion-service-build-") as directory:
        temporary = Path(directory)
        source_root = temporary / "source"
        source_snapshot = stage_sources(ROOT, source_root, (*FILES, "package.py"))
        build_identity = stamp(source_root, version, channel)
        arguments = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--noupx",
            "--onedir",
            "--name",
            "kyrion-service",
            "--paths",
            str(source_root),
            "--distpath",
            str(temporary / "dist"),
            "--workpath",
            str(temporary / "work"),
            "--specpath",
            str(temporary),
        ]
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
                str(source_root / relative) + ":" + str(Path(relative).parent),
            ]
        if channel is not None:
            arguments += [
                "--add-data",
                str(source_root / "installer-channel.json") + ":.",
            ]
        # Include exact installed runtime-package legal material. No user files.
        for package in ("cryptography", "cffi", "pycparser", "pyinstaller"):
            distribution = importlib.metadata.distribution(package)
            for relative in distribution.files or ():
                if "license" in str(relative).lower() and ".dist-info/" in str(
                    relative
                ).replace("\\", "/"):
                    source = Path(distribution.locate_file(relative))
                    if source.is_file() and source.stat().st_size <= 1024**2:
                        arguments += [
                            "--add-data",
                            str(source) + ":third-party-licenses/" + package,
                        ]
        arguments += [str(source_root / "guided.py")]
        subprocess.run(
            arguments,
            check=True,
            timeout=600,
            env={**os.environ, "PYINSTALLER_CONFIG_DIR": str(temporary / "cache")},
        )
        profile = temporary / "dist/kyrion-service"
        probe = subprocess.run(
            [str(profile / "kyrion-service.exe"), "--probe"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        value = json.loads(probe.stdout)
        if value["system"] != "Windows" or value["architecture"] != "amd64":
            raise ValueError("E_SERVICE_HOST_SMOKE")
        version_probe = subprocess.run(
            [str(profile / "kyrion-service.exe"), "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        if version_probe.stdout.strip() != version:
            raise ValueError("E_SERVICE_HOST_BUILD_VERSION")
        channel_probe = subprocess.run(
            [str(profile / "kyrion-service.exe"), "--channel-info"],
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
            raise ValueError("E_SERVICE_HOST_BUILD_CHANNEL")
        if any(path.is_symlink() for path in profile.rglob("*")):
            raise ValueError("E_SERVICE_HOST_LINK")
        if source_snapshot != {name: sha256(ROOT / name) for name in source_snapshot}:
            raise ValueError("E_SERVICE_HOST_SOURCE_CHANGED")
        shutil.copytree(profile, output)

        source_metadata = {
            "schemaVersion": 1,
            "format": "onedir",
            "python": platform.python_version(),
            "cryptography": importlib.metadata.version("cryptography"),
            "pyinstaller": importlib.metadata.version("pyinstaller"),
            "sources": source_snapshot,
            "embeddedVersion": version,
            "embeddedVersionVerified": True,
            "releaseChannelSha256": build_identity.get("releaseChannelSha256"),
            "embeddedChannelVerified": True,
            "serviceRegistrationAccepted": False,
            "coldBootVerified": False,
        }
        (output / "build-source.json").write_text(
            json.dumps(source_metadata, sort_keys=True, indent=2) + "\n"
        )
    return {
        "nativeSmokeTest": True,
        "serviceRegistrationAccepted": False,
        "coldBootVerified": False,
        "format": "onedir",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version")
    parser.add_argument("--channel", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.version, args.channel)))
