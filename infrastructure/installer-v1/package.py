"""Build a reviewed-source Python installer archive, never include host data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

GATEWAY_FILES = tuple(
    "kyrion_gateway_agent/" + name
    for name in (
        "__init__.py",
        "bluetooth.py",
        "cli.py",
        "client.py",
        "config.py",
        "enrollment.py",
        "health.py",
        "lan_transport.py",
        "media_player.py",
        "prepared_runtime.py",
    )
)

FILES = (
    "schema_support.py",
    "guided.py",
    "build_identity.py",
    "release_channel.py",
    "public_https.py",
    "public-ca/cacert.pem",
    "public-ca/metadata.json",
    "public-ca/LICENSE",
    "install_download.py",
    "linux_crypto.py",
    "linux_packages.py",
    "linux_runtime.py",
    "host.py",
    "system_tools.py",
    "hardware_inventory.py",
    "bundle.py",
    "crypto_support.py",
    "native_bundle.py",
    "native_runtime.py",
    "native_backup.py",
    "native_verify_backup.py",
    "backup_policy.py",
    "backup_store.py",
    "backup_schedule.py",
    "backup_worker.py",
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
    "linux_startup.py",
    "docker_images.py",
    "onboarding.py",
    "device_management.py",
    "node_transport.py",
    "node_entry.py",
    "node_service.py",
    "node_pairing.py",
    "identity_settings.py",
    "bootstrap_maintenance.py",
    "error_guidance.py",
    "linked_onboarding.py",
    "verify.py",
    "maintenance.py",
    "update_worker.py",
    "update_automatic.py",
    "update_schedule.py",
    "update_download.py",
    "update_gate.py",
    "update_state.py",
    "update_database.py",
    "update_data.py",
    "update_transaction.py",
    "update_native.py",
    "update_compose.py",
    "recovery.py",
    "release_policy.py",
    "models.py",
    "local_listeners.py",
    "ollama_runtime.py",
    "ollama_models.py",
    "model_cache.py",
    "model-catalog.json",
    "locales/en.json",
    "locales/de.json",
    "templates/compose.yml",
    "templates/Caddyfile",
) + GATEWAY_FILES


def source_file(root: Path, name: str) -> Path:
    if (
        not re.fullmatch(r"[A-Za-z0-9_./-]+", name)
        or name.startswith("/")
        or any(part.startswith(".") for part in Path(name).parts)
    ):
        raise ValueError("E_PACKAGE_SOURCE")
    # Only the real source checkout can supply enumerated sibling component
    # inputs. Sealed build roots contain their own immutable copies instead.
    source_root = Path(__file__).resolve().parent
    if (
        name in GATEWAY_FILES
        and root.resolve() == source_root
        and source_root.name == "installer-v1"
        and source_root.parent.name == "infrastructure"
    ):
        return Path(__file__).resolve().parents[2] / "services/gateway-agent/src" / name
    return root / name


def build(output: Path) -> None:
    from host import reject_links

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
                path = source_file(source, name)
                reject_links(path)
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
