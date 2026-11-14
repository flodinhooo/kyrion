"""Database readiness checks with injected Docker responses, never real services."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from update_compose import Compose


class DatabaseReadiness(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.adapter = object.__new__(Compose)
        self.adapter.root = Path(temporary.name)
        self.adapter.installation = SimpleNamespace(
            state={
                "installationId": "fixture-installation",
                "runtimeImageIds": {"postgres": "sha256:" + "a" * 64},
            }
        )
        self.adapter.compose = Mock(return_value=b"b" * 64)
        self.container = {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": "kyrion-fixture-installation",
                    "com.docker.compose.service": "postgres",
                }
            },
            "Image": "sha256:" + "a" * 64,
            "Mounts": [
                {
                    "Type": "bind",
                    "Destination": "/var/lib/postgresql/data",
                    "Source": str(self.adapter.root / "data/postgres"),
                }
            ],
            "State": {
                "Running": True,
                "Status": "running",
                "Health": {"Status": "healthy"},
            },
        }

    def responses(self, *containers):
        responses = iter(containers)

        def run(operation, *_arguments):
            return (
                json.dumps([next(responses)]).encode()
                if operation == "inspect"
                else b""
            )

        self.adapter.run = Mock(side_effect=run)

    def test_previous_clean_exit_requires_current_daemon_health(self):
        stopped = copy.deepcopy(self.container)
        stopped["State"] = {
            "Running": False,
            "Status": "exited",
            "ExitCode": 0,
            "Health": {"Status": "unhealthy"},
        }
        starting = copy.deepcopy(self.container)
        starting["State"]["Health"]["Status"] = "starting"
        self.responses(stopped, starting, self.container)
        with patch("update_compose.time.sleep") as sleep:
            self.adapter.ensure_database()
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(self.adapter.run.call_count, 4)
        self.adapter.run.assert_any_call("start", "b" * 64)
        self.assertNotIn("--wait", self.adapter.compose.call_args_list[0].args)

    def test_core_readiness_requires_its_own_image_and_knowledge_mount(self):
        self.adapter.installation.state["runtimeImageIds"]["core"] = (
            "sha256:" + "c" * 64
        )
        self.container["Image"] = "sha256:" + "c" * 64
        self.container["Config"]["Labels"]["com.docker.compose.service"] = "core"
        self.container["Mounts"][0].update(
            Destination="/var/lib/kyrion/knowledge",
            Source=str(self.adapter.root / "data/knowledge"),
        )
        self.responses(self.container)
        self.adapter.wait_service("core")
        self.container["Mounts"][0]["Source"] = str(self.adapter.root / "foreign")
        self.responses(self.container)
        with self.assertRaisesRegex(ValueError, "E_BACKUP_SERVICE_RECOVERY"):
            self.adapter.wait_service("core")

    def test_readiness_never_starts_an_arbitrary_service(self):
        with self.assertRaisesRegex(ValueError, "E_UPDATE_SOURCE_COMPONENTS"):
            self.adapter.wait_service("foreign")
        self.adapter.compose.assert_not_called()

    def test_database_exiting_again_is_not_restarted_repeatedly(self):
        stopped = copy.deepcopy(self.container)
        stopped["State"] = {
            "Running": False,
            "Status": "exited",
            "ExitCode": 0,
            "Health": {"Status": "unhealthy"},
        }
        self.responses(stopped, stopped)
        with (
            patch("update_compose.time.sleep"),
            self.assertRaisesRegex(ValueError, "E_UPDATE_DATABASE_HEALTH"),
        ):
            self.adapter.ensure_database()
        starts = [
            call for call in self.adapter.run.call_args_list if call.args[0] == "start"
        ]
        self.assertEqual(len(starts), 1)

    def test_foreign_container_image_or_data_mount_never_establishes_readiness(self):
        for key in ("project", "service", "image", "mount"):
            candidate = copy.deepcopy(self.container)
            if key in {"project", "service"}:
                candidate["Config"]["Labels"]["com.docker.compose." + key] = "foreign"
            elif key == "image":
                candidate["Image"] = "sha256:" + "c" * 64
            else:
                candidate["Mounts"][0]["Source"] = str(self.adapter.root / "foreign")
            self.responses(candidate)
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValueError, "E_UPDATE_DATABASE_TARGET"),
            ):
                self.adapter.ensure_database()

    def test_failed_or_unhealthy_database_fails_without_retrying_start(self):
        for state in (
            {"Status": "exited", "ExitCode": 1},
            {"Status": "running", "Running": True, "Health": {"Status": "unhealthy"}},
            {"Status": "dead", "Dead": True},
            {"Status": "running", "OOMKilled": True},
        ):
            candidate = copy.deepcopy(self.container)
            candidate["State"] = state
            self.responses(candidate)
            with (
                self.subTest(state=state),
                self.assertRaisesRegex(ValueError, "E_UPDATE_DATABASE_HEALTH"),
            ):
                self.adapter.ensure_database()
            self.assertEqual(self.adapter.run.call_count, 1)

    def test_clean_exit_without_restart_times_out_without_success(self):
        self.container["State"] = {"Status": "exited", "ExitCode": 0, "Running": False}
        self.adapter.run = Mock(return_value=json.dumps([self.container]).encode())
        with (
            patch("update_compose.time.sleep"),
            patch("update_compose.time.monotonic", return_value=0),
            self.assertRaisesRegex(ValueError, "E_UPDATE_DATABASE_HEALTH"),
        ):
            self.adapter.ensure_database()
        self.assertEqual(self.adapter.run.call_count, 66)
