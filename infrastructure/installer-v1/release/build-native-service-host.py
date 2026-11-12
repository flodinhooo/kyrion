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


def build(output: Path) -> dict:
    if platform.system() != "Windows" or platform.machine().lower() not in {
        "amd64",
        "x86_64",
    }:
        raise ValueError("E_SERVICE_HOST_BUILD_PLATFORM")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("E_SERVICE_HOST_BUILD_TARGET")
    sys.path.insert(0, str(ROOT))
    from bundle import sha256
    from package import FILES
    from source_snapshot import stage_sources

    with tempfile.TemporaryDirectory(prefix="kyrion-service-build-") as directory:
        temporary = Path(directory)
        source_root = temporary / "source"
        source_snapshot = stage_sources(ROOT, source_root, (*FILES, "package.py"))
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
    args = parser.parse_args()
    print(json.dumps(build(args.output)))
