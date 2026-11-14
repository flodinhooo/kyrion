"""Actual portable GnuPG/deep-path recovery; optional admin boundary injection."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bundle import sha256
from host import reject_links
from native_bundle import authenticated_review
from recovery import create_archive, crypto, verified_plaintext
from windows_system import base_environment, system_directory


def exercise(
    bundle: Path, key: Path, payload: Path, work: Path, *, inject_admin: bool
) -> dict:
    if os.name != "nt" or not work.is_dir():
        raise ValueError("E_TEST_PLATFORM")
    for path in (bundle, key, payload, work):
        reject_links(path)
    reviewed = authenticated_review(bundle, key)
    prefix = "runtime/installer/gnupg/"
    selected = {
        row["path"]: row
        for row in reviewed.manifest["files"]
        if row["path"].startswith(prefix)
    }
    if (
        not {
            prefix + "bin/" + name
            for name in ("gpg.exe", "gpgconf.exe", "gpg-agent.exe")
        }
        <= selected.keys()
    ):
        raise ValueError("E_TEST_RUNTIME")
    for name, row in selected.items():
        path = payload / name
        reject_links(path)
        if (
            not path.is_file()
            or path.stat().st_size != row["bytes"]
            or sha256(path) != row["sha256"]
        ):
            raise ValueError("E_TEST_RUNTIME")
    actual = {
        path.relative_to(payload).as_posix()
        for path in (payload / prefix).rglob("*")
        if path.is_file()
    }
    if actual != selected.keys():
        raise ValueError("E_TEST_RUNTIME_UNTRACKED")
    root = work / ("gpg-path-" + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    # Synthetic developer data still receives an explicit current-user/SYSTEM ACL.
    subprocess.run(
        [
            str(system_directory() / "WindowsPowerShell/v1.0/powershell.exe"),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; $item=([Console]::In.ReadToEnd() | ConvertFrom-Json); $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; $acl=New-Object System.Security.AccessControl.DirectorySecurity; $acl.SetSecurityDescriptorSddlForm(('D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+$sid+')'),[System.Security.AccessControl.AccessControlSections]::Access); (Get-Item -LiteralPath $item.path).SetAccessControl($acl)",
        ],
        input=json.dumps({"path": str(root)}).encode(),
        capture_output=True,
        timeout=30,
        check=True,
        env=base_environment(),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    (root / "fixture.json").write_text(
        json.dumps(
            {
                "scope": "installer-native-gpg-development-fixture",
                "manifestSha256": reviewed.manifest_sha256,
            }
        )
    )
    deep = root / ("deep-" + "a" * 60)
    deep.mkdir()
    source = deep / "synthetic-data"
    source.write_bytes(b"Synthetic portable GnuPG recovery test data")
    archive, encrypted = deep / "fixture.tar", deep / "fixture.gpg"
    create_archive(
        {"database.dump": source}, {"postgresMajor": 17, "schema": 49}, archive
    )
    security = root / "fixture-state"
    security.write_bytes(b"Synthetic ACL source; not an installation identity")
    password = "Synthetic-portable-GnuPG-test-password-123456"
    binary = payload / prefix / "bin/gpg.exe"
    homes = set()
    actual_run = subprocess.run

    def run(arguments, **options):
        if "--homedir" in arguments:
            home = Path(arguments[arguments.index("--homedir") + 1])
            homes.add(str(home))
            if len(str(home).encode("utf-8")) > 80:
                raise ValueError("E_TEST_AGENT_PATH")
            if not inject_admin:
                from native_runtime import permissions

                permissions(home, "root-only")
        return actual_run(arguments, **options)

    with contextlib.ExitStack() as stack:
        if inject_admin:
            # Never write the machine ProgramFiles in a non-elevated developer test.
            stack.enter_context(
                patch(
                    "windows_system.program_files_directory",
                    return_value=Path(tempfile.gettempdir()),
                )
            )
            stack.enter_context(patch("native_runtime.permissions"))
            stack.enter_context(
                patch(
                    "windows_security.create_private_directory",
                    side_effect=lambda path: path.mkdir(mode=0o700),
                )
            )
        stack.enter_context(patch("recovery.subprocess.run", side_effect=run))
        crypto(
            archive,
            encrypted,
            password,
            executable=binary,
            environment=base_environment(),
            security_source=security,
        )
        with verified_plaintext(
            encrypted,
            password,
            executable=binary,
            environment=base_environment(),
            private_parent=deep,
            security_source=security,
        ) as (_clear, manifest, _scratch):
            if manifest["files"]["database.dump"]["sha256"] != sha256(source):
                raise ValueError("E_TEST_ROUNDTRIP")
        try:
            with verified_plaintext(
                encrypted,
                password + "-wrong",
                executable=binary,
                environment=base_environment(),
                private_parent=deep,
                security_source=security,
            ):
                raise ValueError("E_TEST_WRONG_PASSWORD_ACCEPTED")
        except ValueError as error:
            if str(error) != "E_BACKUP_INTEGRITY":
                raise
    if not homes or any(Path(home).exists() for home in homes):
        raise ValueError("E_TEST_AGENT_CLEANUP")
    report = {
        "scope": "installer-native-gpg-development-fixture",
        "manifestSha256": reviewed.manifest_sha256,
        "gpgSha256": sha256(binary),
        "actualPortableGnuPG": True,
        "deepDataParentCharacters": len(str(deep)),
        "maximumAgentHomeBytes": max(len(home.encode("utf-8")) for home in homes),
        "encryptedArchiveRoundtrip": True,
        "wrongPasswordRejected": True,
        "agentHomesRemoved": True,
        "administratorPolicyInjected": inject_admin,
        "actualProgramFilesAgentAclAccepted": not inject_admin,
        "actualDatabaseOrScmAcceptance": False,
    }
    (root / "report.json").write_text(json.dumps(report, indent=2))
    return {"report": str(root / "report.json"), **report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("bundle", "key", "payload", "work"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--inject-admin-policy", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            exercise(
                args.bundle,
                args.key,
                args.payload,
                args.work,
                inject_admin=args.inject_admin_policy,
            )
        )
    )
