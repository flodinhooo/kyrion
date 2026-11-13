"""Actual native recovery-format interoperability, synthetic data only."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "release")]
from bundle import sha256
from gpg_profile import verify_profile
from recovery import crypto
from windows_system import base_environment


def exercise(runtime: Path, legacy: Path | None = None) -> dict:
    if os.name != "nt":
        raise ValueError("E_GPG_FIXTURE_WINDOWS_REQUIRED")
    metadata = verify_profile(runtime)
    directories = {
        path.relative_to(runtime).as_posix()
        for path in runtime.rglob("*")
        if path.is_dir()
    }
    native = runtime / "bin/gpg.exe"
    with tempfile.TemporaryDirectory(prefix="kyrion-gpg-native-test-") as directory:
        root = Path(directory)
        environment = base_environment()
        environment.update(
            HOME=str(root),
            USERPROFILE=str(root),
            APPDATA=str(root / "appdata"),
            LOCALAPPDATA=str(root / "localappdata"),
            TEMP=str(root),
            TMP=str(root),
        )
        (root / "appdata").mkdir()
        (root / "localappdata").mkdir()
        version = (
            subprocess.run(
                [str(native), "--version"],
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=True,
                timeout=20,
            )
            .stdout.decode("utf-8")
            .splitlines()[0]
        )
        if version != "gpg (GnuPG) " + metadata["version"]:
            raise ValueError("E_GPG_FIXTURE_VERSION")
        source = root / "synthetic-input"
        source.write_bytes(b"synthetic operational backup material\n" * 4096)
        password = "Synthetic-native-recovery-password-123456"
        encrypted, clear = root / "native.gpg", root / "native-clear"
        crypto(source, encrypted, password, executable=native, environment=environment)
        crypto(
            encrypted, clear, password, True, executable=native, environment=environment
        )
        if sha256(source) != sha256(clear):
            raise ValueError("E_GPG_FIXTURE_ROUNDTRIP")
        try:
            crypto(
                encrypted,
                root / "wrong-password",
                password + "incorrect",
                True,
                executable=native,
                environment=environment,
            )
        except ValueError as error:
            if str(error) != "E_BACKUP_INTEGRITY":
                raise
        else:
            raise ValueError("E_GPG_FIXTURE_BAD_PASSWORD_ACCEPTED")
        if legacy is not None:
            legacy_clear, legacy_encrypted, native_clear = (
                root / "legacy-clear",
                root / "legacy.gpg",
                root / "converted-clear",
            )
            crypto(
                encrypted,
                legacy_clear,
                password,
                True,
                executable=legacy,
                environment=environment,
            )
            crypto(
                source,
                legacy_encrypted,
                password,
                executable=legacy,
                environment=environment,
            )
            crypto(
                legacy_encrypted,
                native_clear,
                password,
                True,
                executable=native,
                environment=environment,
            )
            if sha256(source) != sha256(legacy_clear) or sha256(source) != sha256(
                native_clear
            ):
                raise ValueError("E_GPG_FIXTURE_INTEROPERABILITY")
        if verify_profile(runtime) != metadata or directories != {
            path.relative_to(runtime).as_posix()
            for path in runtime.rglob("*")
            if path.is_dir()
        }:
            raise ValueError("E_GPG_FIXTURE_PAYLOAD_CHANGED")
        return {
            "version": metadata["version"],
            "gpgSha256": sha256(native),
            "actualNativeRecoveryRoundtrip": True,
            "wrongPasswordRejected": True,
            "legacyInteropBothDirections": legacy is not None,
            "payloadUnchanged": True,
            "systemInstallerExecuted": False,
            "servicesRegistered": False,
            "productionDataUsed": False,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--legacy-gpg", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = exercise(
        args.runtime.resolve(), args.legacy_gpg.resolve() if args.legacy_gpg else None
    )
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
