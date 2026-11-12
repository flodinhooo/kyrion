"""Real owner/group/protected-DACL preservation on own temporary Windows files."""

import ctypes
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime import atomic_json
from windows_security import open_secured_file


@unittest.skipUnless(os.name == "nt", "Windows file security SDK")
class FileSecurity(unittest.TestCase):
    def test_native_exclusive_creation_refuses_existing_file_without_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "managed-key"
            descriptor = open_secured_file(path, root)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(b"preserve existing bytes")
            with self.assertRaisesRegex(OSError, "E_NATIVE_FILE_CREATE"):
                open_secured_file(path, root)
            self.assertEqual(path.read_bytes(), b"preserve existing bytes")

    def test_atomic_replace_preserves_native_owner_group_and_protected_dacl(self):
        from ctypes import wintypes as w

        api = ctypes.WinDLL("advapi32", use_last_error=True)
        api.GetFileSecurityW.argtypes = [
            w.LPCWSTR,
            w.DWORD,
            ctypes.c_void_p,
            w.DWORD,
            ctypes.POINTER(w.DWORD),
        ]
        api.GetFileSecurityW.restype = w.BOOL
        api.SetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.c_void_p]
        api.SetFileSecurityW.restype = w.BOOL

        def descriptor(path):
            size = w.DWORD()
            api.GetFileSecurityW(str(path), 7, None, 0, ctypes.byref(size))
            value = ctypes.create_string_buffer(size.value)
            self.assertTrue(
                api.GetFileSecurityW(
                    str(path), 7, value, len(value), ctypes.byref(size)
                )
            )
            return value

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            atomic_json(path, {"generation": 1})
            original = descriptor(path)
            self.assertTrue(api.SetFileSecurityW(str(path), 0x80000007, original))
            before = descriptor(path).raw
            atomic_json(path, {"generation": 2}, security_source=path)
            self.assertEqual(descriptor(path).raw, before)
            self.assertEqual(json.loads(path.read_text()), {"generation": 2})

    def test_failed_policy_application_never_replaces_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            atomic_json(path, {"generation": 1})
            before = path.read_bytes()
            with (
                patch(
                    "windows_security.copy_file_security",
                    side_effect=OSError("synthetic ACL refusal"),
                ),
                self.assertRaises(OSError),
            ):
                atomic_json(path, {"generation": 2}, security_source=path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])
