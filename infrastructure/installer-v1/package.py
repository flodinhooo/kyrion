"""Build a reviewed-source Python installer archive, never include host data."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

FILES = (
    "guided.py",
    "build_identity.py",
    "host.py",
    "bundle.py",
    "crypto_support.py",
    "native_bundle.py",
    "native_runtime.py",
    "native_backup.py",
    "authority.py",
    "portable_database.py",
    "operational_restore.py",
    "restore_platform.py",
    "restore_material.py",
    "native_staging.py",
    "native_roles.py",
    "native_recovery.py",
    "native_web_transport.py",
    "windows_network.py",
    "windows_service.py",
    "windows_host.py",
    "windows_security.py",
    "windows_system.py",
    "windows_process.py",
    "windows_tasks.py",
    "windows-permissions.ps1",
    "windows-task-security.ps1",
    "windows-tasks.ps1",
    "runtime.py",
    "onboarding.py",
    "identity_settings.py",
    "bootstrap_maintenance.py",
    "error_guidance.py",
    "linked_onboarding.py",
    "verify.py",
    "maintenance.py",
    "update_worker.py",
    "update_schedule.py",
    "update_download.py",
    "recovery.py",
    "release_policy.py",
    "models.py",
    "model_cache.py",
    "model-catalog.json",
    "locales/en.json",
    "locales/de.json",
    "templates/compose.yml",
    "templates/Caddyfile",
)


def build(output: Path) -> None:
    source = Path(__file__).resolve().parent
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("E_PACKAGE: new output file in an existing directory required")
    # No extractall: stage only the exact reviewed member names, with private
    # permissions. No tests, caches, release keys, images or .env enter a package.
    main = """import os, sys, tempfile, zipfile
from pathlib import Path
if sys.version_info < (3, 12):
    raise SystemExit("E_PYTHON: Python 3.12 or newer is required")
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix="kyrion-installer-") as directory:
    root = Path(directory)
    with zipfile.ZipFile(sys.argv[0]) as archive:
        for name in FILES:
            value = archive.read(name)
            if len(value) > 1024 * 1024:
                raise SystemExit("E_PACKAGE: invalid installer member")
            path = root / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes(value)
    sys.path.insert(0, str(root))
    from guided import main
    raise SystemExit(main())
"""
    main = "FILES = " + repr(FILES) + "\n" + main
    with output.open("xb") as stream:
        stream.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(
            stream, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in FILES:
                path = source / name
                if path.is_symlink() or not path.is_file():
                    raise ValueError("E_PACKAGE: missing reviewed source")
                archive.writestr(name, path.read_bytes())
            archive.writestr("__main__.py", main.encode("utf-8"))
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    print(
        json.dumps(
            {
                "artifact": output.name,
                "bytes": output.stat().st_size,
                "sha256": digest,
                "signed": False,
                "requiresPython": "3.12+",
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)


if __name__ == "__main__":
    main()
