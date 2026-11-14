"""Pinned no-pull helper plans; Docker execution is injected here."""

import copy
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import restore_platform
from runtime import Installation
from update_compose import Compose


class ComposeHelpers(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def update_adapter(self):
        identifier = str(uuid.uuid4())
        config = {
            "hostname": "fixture.test",
            "address": "127.0.0.1",
            "release": "1.0.0",
            "manifestSha256": "a" * 64,
            "architecture": "linux/amd64",
        }
        value = {
            "formatVersion": 1,
            "id": identifier,
            "phase": "preparing",
            "directory": "transaction/" + uuid.UUID(identifier).hex[:16],
            "source": config,
            "target": copy.deepcopy(config),
            "files": {".env": {}, "compose.yml": {}},
            "targetImages": {"core": "sha256:" + "b" * 64},
        }
        adapter = object.__new__(Compose)
        adapter.root = self.root
        adapter.installation = SimpleNamespace(
            target=self.root,
            state={
                "installationId": str(uuid.uuid4()),
                "updateTransaction": value,
                "files": {},
            },
            write=Mock(),
        )
        adapter.run = Mock(return_value=b"")
        return adapter

    def test_update_helper_never_pulls_without_unsupported_compose_run_flag(self):
        adapter = self.update_adapter()
        adapter.admin("prepare", schema=49)
        text = adapter.installation.write.call_args.args[1]
        self.assertIn("image: sha256:" + "b" * 64, text)
        self.assertIn("pull_policy: never", text)
        arguments = adapter.run.call_args.args
        self.assertIn("run", arguments)
        self.assertNotIn("--pull", arguments)
        self.assertIn("--no-deps", arguments)
        self.assertIn("--prepare", arguments)

    def test_update_rejects_mutable_or_injected_image_before_execution(self):
        adapter = self.update_adapter()
        adapter.installation.state["updateTransaction"]["targetImages"]["core"] = (
            "registry/foreign:latest\n    pull_policy: always"
        )
        with self.assertRaisesRegex(ValueError, "E_UPDATE_IMAGE"):
            adapter.admin("prepare", schema=49)
        adapter.run.assert_not_called()
        adapter.installation.write.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux restore path syntax")
    def test_restore_helper_uses_the_same_no_pull_policy_and_image_pin(self):
        installation = Installation(
            self.root / "installed",
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        installation.state["runtimeImageIds"] = {"core": "sha256:" + "b" * 64}
        receipt = installation.target / "receipt.json"
        receipt.write_bytes(b"{}")
        adapter = restore_platform.Compose(installation, check_capability=False)
        with patch.object(
            restore_platform,
            "run_system_command",
            return_value=subprocess.CompletedProcess([], 0),
        ) as run:
            adapter.apply_disposition(receipt)
        arguments = run.call_args.args[0]
        self.assertNotIn("--pull", arguments)
        helper = installation.target / "restore-helper.yml"
        self.assertIn(str(helper), arguments)
        self.assertIn("pull_policy: never", helper.read_text())
        self.assertIn("image: sha256:" + "b" * 64, helper.read_text())

    def test_restore_rejects_missing_or_mutable_image_reference(self):
        adapter = restore_platform.Compose(
            SimpleNamespace(target=self.root, state={}), check_capability=False
        )
        for value in (
            None,
            {},
            {"core": "kyrion/core:latest"},
            {"core": "sha256:short"},
        ):
            adapter.installation.state["runtimeImageIds"] = value
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "E_RESTORE_IMAGE_PIN"),
            ):
                adapter.core_image()
