"""Native SCM read-only checks, pure plans, and no simulated host acceptance."""

import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_roles import role_plan
from windows_service import ServiceManager, service_plan, validate_plan, windows_argv


class Plans(unittest.TestCase):
    def setUp(self):
        self.identifier = str(uuid.uuid4())
        self.root = r"C:\ProgramData\Kyrion"

    def test_distinct_virtual_accounts_and_explicit_dependencies(self):
        plans = [
            service_plan(self.identifier, self.root, role)
            for role in ("postgres", "core", "web", "caddy")
        ]
        self.assertEqual(len({p["account"] for p in plans}), 4)
        self.assertTrue(all(p["account"] == "NT SERVICE\\" + p["name"] for p in plans))
        self.assertEqual(plans[0]["dependencies"], ["RPCSS"])
        for index in range(1, 4):
            self.assertEqual(plans[index]["dependencies"], [plans[index - 1]["name"]])
        self.assertNotIn("password", " ".join(plans[0]["argv"]))

    def test_bootstrap_reuses_only_postgres_identity_without_another_writer(self):
        runtime = service_plan(self.identifier, self.root, "postgres")
        initialization = service_plan(self.identifier, self.root, "postgres-init")
        self.assertEqual(runtime["name"], initialization["name"])
        self.assertEqual(runtime["account"], initialization["account"])
        self.assertEqual(initialization["dependencies"], ["RPCSS"])
        self.assertIn("postgres-init", initialization["argv"])
        self.assertIn("-h 127.0.0.1 -p 5432", runtime["argv"])
        validate_plan(initialization)

    def test_noncanonical_or_changed_service_plan_is_rejected(self):
        for identifier in (
            self.identifier.upper(),
            "{" + self.identifier + "}",
            self.identifier.replace("-", ""),
        ):
            with self.assertRaises(ValueError):
                service_plan(identifier, self.root, "core")
        for role in ("shell", "ai", "postgres-admin"):
            with self.assertRaises(ValueError):
                service_plan(self.identifier, self.root, role)
        plan = service_plan(self.identifier, self.root, "core")
        for field, value in (
            ("account", "LocalSystem"),
            ("argv", ["cmd.exe"]),
            ("dependencies", []),
        ):
            with self.assertRaisesRegex(ValueError, "E_SERVICE_PLAN"):
                validate_plan({**plan, field: value})

    def test_runtime_environment_does_not_inherit_credentials_or_injection(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    "KYRION_DATABASE_PASSWORD": "private",
                    "JAVA_TOOL_OPTIONS": "injected",
                    "NODE_OPTIONS": "injected",
                    "SPOTIFY_CLIENT_SECRET": "private",
                    "SystemRoot": "C:/untrusted",
                    "PSModulePath": "C:/untrusted-modules",
                },
            ),
        ):
            root = Path(directory)
            config = {
                "hostname": "fixture.test",
                "address": "127.0.0.1",
                "ports": {
                    "core": 18080,
                    "web": 13000,
                    "postgres": 15432,
                    "caddy": 14443,
                },
            }
            for role in ("core", "web", "caddy"):
                executable, arguments, environment = role_plan(root, role, config)
                self.assertTrue(executable.is_relative_to(root / "payload/runtime"))
                self.assertNotIn("KYRION_DATABASE_PASSWORD", environment)
                self.assertNotIn("SPOTIFY_CLIENT_SECRET", environment)
                self.assertNotEqual(environment["SystemRoot"], "C:/untrusted")
                self.assertNotEqual(environment["PSModulePath"], "C:/untrusted-modules")
                self.assertEqual(environment["JAVA_TOOL_OPTIONS"], "")
                self.assertEqual(environment["NODE_OPTIONS"], "")
                self.assertNotIn("private", " ".join(arguments))
                self.assertEqual(
                    environment["APPDATA"], str(root / "data" / role / "appdata")
                )
            _, _, core = role_plan(root, "core", config)
            self.assertEqual(core["KYRION_AI_BASE_URL"], "http://127.0.0.1:9")
            self.assertEqual(
                core["KYRION_DATABASE_PASSWORD_FILE"],
                str(root / "secrets/postgres-password"),
            )

    @unittest.skipUnless(
        os.name == "nt", "Native directory creation refuses existing data"
    )
    def test_private_create_never_replaces_an_existing_directory(self):
        from windows_security import create_private_directory

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            sentinel = target / "operator-data"
            sentinel.write_bytes(b"preserve original")
            with self.assertRaises((ValueError, OSError)):
                create_private_directory(target)
            self.assertEqual(sentinel.read_bytes(), b"preserve original")
            self.assertEqual(list(target.iterdir()), [sentinel])

    @unittest.skipUnless(os.name == "nt", "Actual native token identity refusal")
    def test_current_interactive_user_is_not_a_virtual_service_account(self):
        from windows_security import assert_identity

        with self.assertRaisesRegex(ValueError, "E_NATIVE_IDENTITY"):
            assert_identity("TrustedInstaller")

    @unittest.skipUnless(os.name == "nt", "Native Windows command parser")
    def test_windows_native_command_parser_matches_bounded_plans(self):
        for role in ("postgres", "core", "web", "caddy"):
            argv = service_plan(
                self.identifier, r"C:\ProgramData\Kyrion Native Test", role
            )["argv"]
            self.assertEqual(windows_argv(subprocess.list2cmdline(argv)), argv)

    @unittest.skipUnless(os.name == "nt", "Read-only native SCM query")
    def test_native_scm_read_only_missing_service(self):
        with (
            ServiceManager() as scm,
            scm.opened("Kyrion-" + self.identifier + "-core") as handle,
        ):
            self.assertIsNone(handle)

    @unittest.skipUnless(
        os.name == "nt", "Actual read-only native service configuration"
    )
    def test_native_query_layout_and_foreign_service_refusal(self):
        with ServiceManager() as scm, scm.opened("TrustedInstaller") as handle:
            self.assertIsNotNone(handle)
            value = scm.query(handle)
            self.assertEqual(value["kind"], 16)
            self.assertIsInstance(value["binary"], str)
            self.assertIsInstance(value["dependencies"], list)
            self.assertIn(value["state"], {1, 2, 3, 4, 5, 6, 7})
            with self.assertRaisesRegex(ValueError, "E_SERVICE_FOREIGN"):
                scm.assert_owned(
                    handle, service_plan(self.identifier, self.root, "core")
                )

    @unittest.skipUnless(
        os.name == "nt", "Actual native security descriptor APIs, memory only"
    )
    def test_native_service_security_policy_rejects_unsafe_memory_descriptors(self):
        import ctypes
        from unittest.mock import patch

        with ServiceManager() as scm:
            w = scm.w
            cases = [
                ("O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)", True),
                ("O:LSG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)", False),
                ("O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GR;;;BU)", False),
                ("O:BAG:BAD:P(A;;GA;;;SY)(A;;GR;;;BA)", False),
                ("O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;BU)", False),
            ]
            for descriptor, accepted in cases:
                with self.subTest(accepted=accepted, descriptor=descriptor):
                    pointer = ctypes.c_void_p()
                    length = w.DWORD()
                    self.assertTrue(
                        scm.api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                            descriptor, 1, ctypes.byref(pointer), ctypes.byref(length)
                        )
                    )

                    def query(
                        _handle,
                        _information,
                        output,
                        capacity,
                        needed,
                        _length=length,
                        _pointer=pointer,
                    ):
                        ctypes.cast(
                            needed, ctypes.POINTER(w.DWORD)
                        ).contents.value = _length.value
                        if not output or capacity < _length.value:
                            return False
                        ctypes.memmove(output, _pointer, _length.value)
                        return True

                    try:
                        with patch.object(
                            scm.api, "QueryServiceObjectSecurity", side_effect=query
                        ):
                            if accepted:
                                scm.assert_security(None)
                            else:
                                with self.assertRaisesRegex(
                                    ValueError, "E_SERVICE_SECURITY"
                                ):
                                    scm.assert_security(None)
                    finally:
                        scm.kernel.LocalFree(pointer)

    @unittest.skipUnless(os.name == "nt", "Native SCM console refusal")
    def test_console_dispatch_never_launches_workload(self):
        from windows_host import dispatch

        called = []
        with self.assertRaisesRegex(OSError, "E_SERVICE_DISPATCH"):
            dispatch(
                "Kyrion-" + self.identifier + "-core", lambda *_: called.append(True)
            )
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
