"""Actual native APIs on owned temporary Windows files, without services/UAC."""

import ctypes
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from windows_test_support import private_root

from kyrion_gateway_agent import windows_storage as storage


@unittest.skipUnless(os.name == "nt", "Actual Windows prepared storage")
class WindowsStorageTests(unittest.TestCase):
    def set_sddl(self, path, extra):
        api = storage.api()
        api.bind(
            api.security,
            "SetFileSecurityW",
            [api.w.LPCWSTR, api.w.DWORD, ctypes.c_void_p],
            api.w.BOOL,
        )
        sddl = "D:P" + "".join("(A;OICI;FA;;;" + sid + ")" for sid in sorted(api.trusted)) + extra
        descriptor = ctypes.c_void_p()
        self.assertTrue(
            api.security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl, 1, ctypes.byref(descriptor), None
            )
        )
        try:
            self.assertTrue(
                api.security.SetFileSecurityW(storage.native_path(path), 0x80000004, descriptor)
            )
        finally:
            api.kernel.LocalFree(descriptor)

    def setUp(self):
        # Some development sandboxes deliberately grant additional identities
        # write access to Temp. Preserve that ACL and test beneath a separately
        # validated, user-owned local data ancestor instead of weakening policy.
        self.root = self.enterContext(private_root())

    def test_actual_private_directory_publication_and_no_overwrite(self):
        path = self.root / "synthetic-agent.json"
        storage.publish(path, b"synthetic private bytes")
        self.assertEqual(storage.read_private(path), b"synthetic private bytes")
        self.assertTrue(storage.api().inspect(path).protected)
        with self.assertRaises(FileExistsError):
            storage.publish(path, b"replacement must not be installed")
        self.assertEqual(storage.read_private(path), b"synthetic private bytes")
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_actual_native_lock_is_exclusive_and_released(self):
        path = self.root / "agent.lock"
        with (
            storage.enrollment_lock(path),
            self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_BUSY"),
            storage.enrollment_lock(path),
        ):
            self.fail("second native handle acquired")
        with storage.enrollment_lock(path):
            pass

    def test_cross_process_lock_refusal_and_acquisition_after_release(self):
        path = self.root / "agent.lock"
        script = (
            "import sys; from pathlib import Path; "
            "from kyrion_gateway_agent.windows_storage import enrollment_lock; "
            "guard=enrollment_lock(Path(sys.argv[1])); "
            "guard.__enter__(); guard.__exit__(None,None,None)"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        with storage.enrollment_lock(path):
            result = subprocess.run(
                [sys.executable, "-c", script, str(path)],
                env=environment,
                capture_output=True,
                timeout=15,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"E_AGENT_ENROLLMENT_BUSY", result.stderr)
        result = subprocess.run(
            [sys.executable, "-c", script, str(path)],
            env=environment,
            capture_output=True,
            timeout=15,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0)

    def test_hard_linked_private_credentials_are_refused(self):
        path, alias = self.root / "private.json", self.root / "alias.json"
        storage.publish(path, b"synthetic private bytes")
        os.link(path, alias)
        with self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_FILE"):
            storage.read_private(path)
        self.assertEqual(path.read_bytes(), b"synthetic private bytes")

    def test_private_read_is_bounded(self):
        path = self.root / "private.json"
        storage.publish(path, b"x" * 32)
        with self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_FILE"):
            storage.read_private(path, maximum=16)

    def test_actual_public_read_grant_on_synthetic_file_is_refused(self):
        path = self.root / "synthetic.json"
        storage.publish(path, b"synthetic private bytes")
        self.set_sddl(path, "(A;;FR;;;WD)")
        with self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_FILE"):
            storage.read_private(path)

    def test_known_folder_lookup_ignores_environment_aliases(self):
        expected = storage.local_data()
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\untrusted-alias"}):
            self.assertEqual(storage.local_data(), expected)

    def test_exclusive_private_directory_creation_refuses_adopting_prior_data(self):
        path = self.root / "prior"
        storage.private_directory(path)
        storage.publish(path / "keep", b"preserve existing data")
        with self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_PATH"):
            storage.private_directory(path, exclusive=True)
        self.assertEqual(storage.read_private(path / "keep"), b"preserve existing data")

    def test_private_temporary_inputs_are_removed_without_recursive_cleanup(self):
        with storage.temporary_directory() as directory:
            storage.publish(directory / "code", b"synthetic private input")
            self.assertEqual(storage.read_private(directory / "code"), b"synthetic private input")
        self.assertFalse(directory.exists())

    def test_actual_symlink_is_refused_when_creation_is_supported(self):
        target, link = self.root / "target", self.root / "link"
        storage.publish(target, b"synthetic private bytes")
        try:
            os.symlink(target, link)
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                self.skipTest("Actual Windows symbolic-link privilege unavailable")
            raise
        try:
            with self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_PATH"):
                storage.read_private(link)
        finally:
            link.unlink()
        self.assertEqual(storage.read_private(target), b"synthetic private bytes")

    def test_actual_writable_ancestor_is_refused_without_creating_child(self):
        parent = self.root / "unsafe"
        storage.private_directory(parent)
        self.set_sddl(parent, "(A;;0x40;;;WD)")
        with self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_PATH"):
            storage.private_directory(parent / "uncreated")
        self.assertFalse((parent / "uncreated").exists())

    def test_exclusive_creation_failure_does_not_remove_an_existing_temporary(self):
        path = self.root / "target.json"
        temporary = self.root / (".target.json." + "a" * 32)
        storage.publish(temporary, b"preserve earlier file")
        with (
            patch(
                "kyrion_gateway_agent.windows_storage.uuid.uuid4", return_value=Mock(hex="a" * 32)
            ),
            self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_FILE"),
        ):
            storage.publish(path, b"must not replace earlier file")
        self.assertEqual(storage.read_private(temporary), b"preserve earlier file")
        self.assertFalse(path.exists())

    def test_completed_native_move_survives_lost_caller_acknowledgement(self):
        path = self.root / "target.json"
        move = storage.api().kernel.MoveFileExW

        def interrupted(*arguments):
            self.assertTrue(move(*arguments))
            raise KeyboardInterrupt()

        with (
            patch.object(storage.api().kernel, "MoveFileExW", interrupted),
            self.assertRaises(KeyboardInterrupt),
        ):
            storage.publish(path, b"synthetic committed bytes")
        self.assertEqual(storage.read_private(path), b"synthetic committed bytes")
        self.assertEqual(path.stat().st_nlink, 1)

    def test_operating_system_releases_lock_after_child_process_termination(self):
        path = self.root / "agent.lock"
        script = (
            "import sys,time; from pathlib import Path; "
            "from kyrion_gateway_agent.windows_storage import enrollment_lock; "
            "guard=enrollment_lock(Path(sys.argv[1])); guard.__enter__(); "
            "print('READY',flush=True); time.sleep(30)"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        with subprocess.Popen(
            [sys.executable, "-c", script, str(path)],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ) as child:
            ready = []
            reader = threading.Thread(
                target=lambda: ready.append(child.stdout.readline()), daemon=True
            )
            reader.start()
            try:
                reader.join(timeout=10)
                self.assertEqual(ready, [b"READY\r\n"])
                with (
                    self.assertRaisesRegex(ValueError, "E_AGENT_ENROLLMENT_BUSY"),
                    storage.enrollment_lock(path),
                ):
                    self.fail("child native lock was not held")
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=10)
                reader.join(timeout=1)
        with storage.enrollment_lock(path):
            pass

    def test_ambiguous_device_and_unc_paths_are_refused(self):
        for value in (
            "relative",
            r"C:\private\secret:stream",
            r"C:\private\CON.json",
            r"C:\private\name.",
            r"\\server\share\private",
        ):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "E_AGENT_PRIVATE_PATH"),
            ):
                storage.native_path(Path(value))
