"""Real file interruption/resume; SCM and elevation are orchestration fixtures."""

import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_runtime
from runtime import Installation


class Cleanup(unittest.TestCase):
    def test_service_removal_waits_until_each_handle_is_closed(self):
        events = []
        manager = MagicMock()
        manager.__enter__.return_value = manager

        @contextlib.contextmanager
        def opened(name, mutate=False):
            yield name
            events.append(("closed", name))

        manager.opened.side_effect = opened
        manager.remove.side_effect = lambda handle, plan: events.append(
            ("removed", handle)
        )

        def wait(name):
            self.assertEqual(events[-1], ("closed", name))
            events.append(("absent", name))

        manager.wait_removed.side_effect = wait
        with (
            patch.object(native_runtime, "permissions"),
            patch.object(native_runtime, "ServiceManager", return_value=manager),
            patch.object(
                native_runtime,
                "plan_for",
                side_effect=lambda installation, role: {"name": role},
            ),
        ):
            native_runtime.stop_services(self.installation, remove=True)
        self.assertEqual(
            [name for event, name in events if event == "absent"],
            list(reversed(native_runtime.ROLES)),
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "installation"
        self.installation = Installation(
            self.root,
            {"release": "1.2.3", "architecture": "windows/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.installation.state["backend"] = "windows-native"
        for name, data in {
            "payload/a.bin": b"public a",
            "payload/b.bin": b"public b",
            "secrets/credential.key": b"private synthetic material",
        }.items():
            self.installation.write(name, data)
        self.installation.state["stage"] = "services-healthy"
        self.installation.save()

    def mark_removed(self):
        self.installation.state["stage"] = "uninstalled"
        self.installation.save()

    def test_missing_payload_requires_recorded_removal_and_does_not_weaken_default(
        self,
    ):
        (self.root / "payload/a.bin").unlink()
        with self.assertRaisesRegex(ValueError, "E_STATE"):
            self.installation.verify_files(removing_payload=True)
        self.mark_removed()
        self.installation.verify_files(removing_payload=True)
        with self.assertRaisesRegex(ValueError, "E_CHANGED"):
            self.installation.verify_files()

    def test_retained_keys_and_changed_remaining_payload_are_still_verified(self):
        self.mark_removed()
        (self.root / "payload/a.bin").unlink()
        (self.root / "payload/b.bin").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "E_CHANGED"):
            self.installation.verify_files(removing_payload=True)
        (self.root / "payload/b.bin").write_bytes(b"public b")
        (self.root / "secrets/credential.key").unlink()
        with self.assertRaisesRegex(ValueError, "E_CHANGED"):
            self.installation.verify_files(removing_payload=True)

    def test_interrupted_software_removal_resumes_and_preserves_data(self):
        manager = MagicMock()
        manager.__enter__.return_value = manager
        manager.opened.return_value = contextlib.nullcontext(None)
        real_remove = native_runtime.shutil.rmtree

        def interrupted(path):
            self.assertEqual(path, self.root / "payload")
            (path / "a.bin").unlink()
            raise PermissionError("synthetic interruption")

        with (
            patch.object(native_runtime, "permissions"),
            patch.object(native_runtime, "ServiceManager", return_value=manager),
            patch.object(native_runtime, "plan_for", return_value={"name": "fixture"}),
            patch.object(native_runtime, "stop_services") as stop,
        ):
            with (
                patch.object(native_runtime.shutil, "rmtree", side_effect=interrupted),
                self.assertRaises(PermissionError),
            ):
                native_runtime.uninstall_native(self.root)
            state = json.loads((self.root / "install-state.json").read_text())
            self.assertEqual(state["stage"], "uninstalled")
            result = native_runtime.uninstall_native(self.root)
            self.assertTrue(result["runtimeRemoved"])
            self.assertFalse(result["dataRemoved"])
            self.assertEqual(
                (self.root / "secrets/credential.key").read_bytes(),
                b"private synthetic material",
            )
            self.assertFalse((self.root / "payload").exists())
            self.assertTrue(
                native_runtime.uninstall_native(self.root)["runtimeRemoved"]
            )
            self.assertEqual(stop.call_count, 3)
        self.assertIs(native_runtime.shutil.rmtree, real_remove)

    def test_repair_after_removal_requires_reviewed_bundle_before_services(self):
        self.mark_removed()
        (self.root / "payload/a.bin").unlink()
        with (
            patch.object(native_runtime, "permissions"),
            patch.object(native_runtime, "ServiceManager") as scm,
            self.assertRaisesRegex(ValueError, "E_NATIVE_SIGNED_BUNDLE_REQUIRED"),
        ):
            native_runtime.repair_native(self.root)
        scm.assert_not_called()
        self.assertTrue((self.root / "secrets/credential.key").is_file())
