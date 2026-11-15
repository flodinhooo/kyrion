"""Node service policy and profile boundaries, with explicit OS test doubles."""

import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import node_service
from recovery import load_installation


class NodeServiceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux filesystem fixture")
    def test_new_unit_does_not_reset_unloaded_failure_state(self):
        import os

        for active in ("inactive", "failed"):
            with (
                self.subTest(active=active),
                tempfile.TemporaryDirectory() as temporary,
            ):
                target = Path(temporary)
                (target / "agent").mkdir(mode=0o700)
                (target / "agent/agent.json").write_text("{}", encoding="utf-8")
                worker = "node-worker-" + "a" * 32
                (target / worker).write_bytes(b"synthetic worker, never executed")
                identifier = str(uuid.uuid4())
                installation = SimpleNamespace(
                    target=target,
                    state={"installationId": identifier, "nodeWorker": worker},
                    save=lambda: None,
                )
                account = "kyrion-node-" + uuid.UUID(identifier).hex[:16]
                unit = target / "synthetic.service"

                def systemctl(*args, unit=unit, active=active):
                    if args[0] == "show":
                        return (
                            "LoadState=loaded\nFragmentPath="
                            + str(unit)
                            + "\nDropInPaths=\nActiveState="
                            + active
                        )
                    return ""

                with (
                    patch.object(node_service, "require_host"),
                    patch.object(node_service, "load", return_value=installation),
                    patch.object(
                        node_service,
                        "identity",
                        return_value=(os.geteuid(), os.getegid(), account),
                    ),
                    patch.object(node_service, "owned_unit", return_value=unit),
                    patch.object(node_service, "publish_unit"),
                    patch.object(
                        node_service, "service_state", return_value={"injected": True}
                    ),
                    patch.object(
                        node_service, "systemctl", side_effect=systemctl
                    ) as calls,
                ):
                    node_service.configure(
                        SimpleNamespace(
                            target=target,
                            node_service="repair",
                            node_url=None,
                            node_token_file=None,
                            node_certificate=None,
                        )
                    )
                resets = [
                    call.args
                    for call in calls.call_args_list
                    if call.args[0] == "reset-failed"
                ]
                self.assertEqual(
                    [("reset-failed", unit.name)] if active == "failed" else [], resets
                )

    def fixture(self):
        identifier = str(uuid.uuid4())
        installation = SimpleNamespace(
            target=PurePosixPath("/var/lib/kyrion-node-fixture"),
            state={"installationId": identifier},
        )
        return installation, "kyrion-node-" + uuid.UUID(identifier).hex[:16]

    def test_service_uses_non_login_account_and_no_login_target(self):
        installation, account = self.fixture()
        text = node_service.definition(installation, "node-worker-" + "a" * 32, account)
        for expected in (
            "User=" + account,
            "Group=" + account,
            "WantedBy=multi-user.target",
            "NoNewPrivileges=yes",
            "CapabilityBoundingSet=",
            "PrivateDevices=yes",
            "ReadWritePaths=/var/lib/kyrion-node-fixture/agent",
            "--background-node --node-config",
            "KillMode=control-group",
            "StartLimitBurst=3",
            "ProtectSystem=strict",
        ):
            self.assertIn(expected, text)
        self.assertNotIn("User=root", text)

    def test_definition_refuses_other_account_and_argument_injection(self):
        installation, account = self.fixture()
        with self.assertRaisesRegex(ValueError, "E_NODE_SERVICE_PLAN"):
            node_service.definition(installation, "node-worker-" + "a" * 32, "root")
        installation.target = Path("/var/lib/node\nExecStart=/bin/sh")
        with self.assertRaisesRegex(ValueError, "E_NODE_SERVICE_PLAN"):
            node_service.definition(installation, "node-worker-" + "a" * 32, account)

    def test_node_journal_never_enters_core_restore_maintenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            path = target / "install-state.json"
            path.write_text(
                json.dumps({"backend": node_service.BACKEND}), encoding="utf-8"
            )
            path.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "E_NODE_PROFILE_OPERATION"):
                load_installation(target)

    def test_wrong_platform_rejected_before_os_actions(self):
        with (
            patch.object(node_service.sys, "platform", "win32"),
            self.assertRaisesRegex(ValueError, "E_NODE_SYSTEMD_REQUIRED"),
        ):
            node_service.require_host(Path("/var/lib/fixture"))

    def test_missing_frozen_worker_refused_before_account_creation(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(node_service, "require_host"),
            patch.object(node_service.sys, "frozen", False, create=True),
            patch.object(node_service, "identity") as account,
        ):
            args = SimpleNamespace(
                target=Path(temporary) / "node", node_service="install"
            )
            with self.assertRaisesRegex(ValueError, "E_STARTUP_FROZEN_REQUIRED"):
                node_service.configure(args)
            account.assert_not_called()

    def test_review_cancel_has_no_system_changes(self):
        args = SimpleNamespace(
            target=Path("/var/lib/fixture"),
            node_service="install",
            node_certificate=None,
        )
        with (
            patch("builtins.input", return_value="CANCEL"),
            patch.object(node_service, "configure") as operation,
            patch(
                "host.inventory",
                return_value={"system": "synthetic", "bootMode": "central-only"},
            ),
        ):
            self.assertEqual(
                0, node_service.guided(args, {"nodeServiceReview": "Review"})
            )
            operation.assert_not_called()
