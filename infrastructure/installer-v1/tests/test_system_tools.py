"""Operational process boundary tests; no real Docker/OS mutation is executed."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recovery
import system_tools as tools


class SystemTools(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Actual Windows known folder API")
    def test_program_files_uses_known_folder_and_preflights_without_creation(self):
        from windows_system import program_files_directory

        parent = program_files_directory()
        self.assertTrue(parent.is_absolute())
        self.assertTrue(parent.is_dir())
        with (
            patch("native_runtime.permissions") as permissions,
            patch("windows_security.create_private_directory") as create,
        ):
            self.assertEqual(recovery.native_crypto_parent(), parent)
        create.assert_not_called()
        self.assertEqual(permissions.call_args.args[0].parent, parent)
        self.assertEqual(permissions.call_args.args[1], "plan-create")

    @unittest.skipUnless(os.name == "nt", "Windows agent socket bound")
    def test_long_native_agent_parent_fails_before_process_or_directory_creation(self):
        with (
            patch(
                "windows_system.program_files_directory",
                return_value=Path("C:/" + "long" * 30),
            ),
            patch("native_runtime.permissions") as permissions,
            patch("windows_security.create_private_directory") as create,
            self.assertRaisesRegex(ValueError, "E_GPG_SOCKET_PARENT"),
        ):
            recovery.native_crypto_parent()
        permissions.assert_not_called()
        create.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Linux protected scratch boundary")
    def test_default_restore_scratch_does_not_use_caller_tmpdir(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"TMPDIR": directory}),
            recovery.private_restore_directory(None, None) as scratch,
        ):
            self.assertEqual(scratch.parent, Path("/tmp"))
            self.assertEqual(scratch.stat().st_mode & 0o777, 0o700)

    @unittest.skipUnless(os.name == "posix", "Linux protected crypto scratch boundary")
    def test_public_plaintext_parent_is_refused_before_password_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            public.mkdir(mode=0o755)
            source = public / "plaintext"
            source.write_bytes(b"synthetic data")
            with (
                patch.object(recovery.subprocess, "run") as run,
                self.assertRaisesRegex(ValueError, "E_RESTORE_PRIVATE_PARENT"),
            ):
                recovery.crypto(source, root / "output", "Synthetic-passphrase-123456")
            run.assert_not_called()

    def test_operational_runner_uses_fixed_executable_and_clean_environment(self):
        with (
            patch.object(tools, "required", return_value=Path("/fixture/docker")),
            patch.object(
                tools.subprocess, "run", return_value=Mock(returncode=0)
            ) as run,
            patch.dict(
                os.environ,
                {
                    "LD_PRELOAD": "never-load",
                    "OPENAI_API_KEY": "never-inherit",
                    "DOCKER_HOST": "tcp://never-connect.invalid:2375",
                },
            ),
        ):
            tools.run(
                ["docker", "version"], capture_output=True, timeout=10, check=False
            )
        self.assertEqual(
            run.call_args.args[0], [str(Path("/fixture/docker")), "version"]
        )
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        for key in ("LD_PRELOAD", "OPENAI_API_KEY", "DOCKER_HOST"):
            self.assertNotIn(key, run.call_args.kwargs["env"])

    def test_unknown_or_missing_tool_stops_before_process_creation(self):
        with (
            patch.object(tools, "executable", return_value=None),
            patch.object(tools.subprocess, "run") as run,
            self.assertRaisesRegex(ValueError, "E_SYSTEM_TOOL"),
        ):
            tools.run(["docker", "version"], timeout=1)
        run.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Linux GnuPG trust boundary")
    def test_unapproved_crypto_binary_never_receives_password(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.write_bytes(b"synthetic data")
            for name in ("gpg", "gpgconf", "gpg-agent"):
                (root / name).write_bytes(b"untrusted fixture; never run")
            with (
                patch.object(tools, "executable", return_value=Path("/usr/bin/gpg")),
                patch.object(recovery.subprocess, "run") as run,
                self.assertRaisesRegex(ValueError, "E_GPG_REQUIRED"),
            ):
                recovery.crypto(
                    source,
                    root / "output",
                    "Synthetic-passphrase-123456",
                    executable=root / "gpg",
                )
            run.assert_not_called()
            self.assertFalse((root / "output").exists())

    @unittest.skipUnless(
        os.name == "nt", "Frozen Windows must use verified portable GnuPG"
    )
    def test_frozen_windows_never_uses_path_gpg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.write_bytes(b"synthetic data")
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(recovery.subprocess, "run") as run,
                self.assertRaisesRegex(ValueError, "E_GPG_REQUIRED"),
            ):
                recovery.crypto(source, root / "output", "Synthetic-passphrase-123456")
            run.assert_not_called()
