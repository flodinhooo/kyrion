"""Required native-host protocols tolerate independent additive capability fields."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from update_native import Native


class NativeCapabilitiesTests(unittest.TestCase):
    def test_required_protocols_are_strict_and_additive_capabilities_are_allowed(self):
        required = {
            "formatVersion": 1,
            "updateProtocol": 1,
            "startupFence": True,
            "maintenanceCore": True,
        }
        with tempfile.TemporaryDirectory() as temporary:
            adapter = Native(Mock(target=Path(temporary)))
            variants = (
                (required, True),
                ({**required, "agentIngressFence": True, "publicHttpsTrust": {}}, True),
                ({**required, "formatVersion": True}, False),
                ({**required, "updateProtocol": 1.0}, False),
                ({**required, "startupFence": 1}, False),
                ({**required, "maintenanceCore": False}, False),
                ([], False),
            )
            for capability, accepted in variants:
                with (
                    self.subTest(capability=capability),
                    patch(
                        "update_native.subprocess.run",
                        return_value=subprocess.CompletedProcess(
                            [], 0, json.dumps(capability).encode(), b""
                        ),
                    ),
                    patch("update_native.subprocess.CREATE_NO_WINDOW", 0, create=True),
                    patch("windows_system.base_environment", return_value={}),
                ):
                    if accepted:
                        adapter.check_host(Path(temporary))
                    else:
                        with self.assertRaisesRegex(
                            ValueError, "E_UPDATE_HOST_UPGRADE_REQUIRED"
                        ):
                            adapter.check_host(Path(temporary))
