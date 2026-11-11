"""Task plans and actual Windows COM schema validation, never registration."""

import json
import os
import subprocess
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_tasks import NAMESPACE, operate, task_plan


class TaskPlanTests(unittest.TestCase):
    def setUp(self):
        self.identifier = str(uuid.uuid4())
        self.plan = task_plan(self.identifier, r"C:\ProgramData\Kyrion Test", "core")

    def test_boot_principal_and_bounded_retry_are_explicit(self):
        root = ET.fromstring(self.plan["xml"])
        ns = {"t": NAMESPACE}
        self.assertIsNotNone(root.find("t:Triggers/t:BootTrigger", ns))
        self.assertIsNone(root.find("t:Triggers/t:LogonTrigger", ns))
        self.assertEqual(
            root.findtext("t:Principals/t:Principal/t:UserId", namespaces=ns),
            "S-1-5-19",
        )
        self.assertIsNone(root.find("t:Principals/t:Principal/t:LogonType", ns))
        self.assertEqual(
            root.findtext("t:Settings/t:RestartOnFailure/t:Count", namespaces=ns), "3"
        )
        self.assertEqual(
            root.findtext("t:Settings/t:MultipleInstancesPolicy", namespaces=ns),
            "IgnoreNew",
        )
        self.assertIn(self.identifier, self.plan["name"])
        self.assertIn('"C:\\ProgramData\\Kyrion Test"', self.plan["arguments"])

    def test_no_network_share_shell_or_root_target(self):
        for value in (
            r"\\server\share\Kyrion",
            "C:\\",
            r"C:\Kyrion\..\Windows",
            r"C:\Data\Kyrion:stream",
            'C:\\Data\\Kyrion"bad',
            r"C:\Data\%USERNAME%\Kyrion",
            "relative/target",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                task_plan(self.identifier, value, "web")
        with self.assertRaises(ValueError):
            task_plan(self.identifier, r"C:\ProgramData\Kyrion", "arbitrary-command")

    def test_modified_input_plan_cannot_be_dispatched(self):
        with self.assertRaisesRegex(ValueError, "E_WINDOWS_TASK_PLAN"):
            operate({**self.plan, "command": r"C:\Windows\System32\cmd.exe"})

    @unittest.skipUnless(os.name == "nt", "Actual Windows security-descriptor parser")
    def test_native_task_security_rejects_shared_or_mutable_descriptors(self):
        script = Path(__file__).parent / "integration/verify-task-security.ps1"
        result = subprocess.run(
            [
                str(
                    Path(os.environ["SystemRoot"])
                    / "System32/WindowsPowerShell/v1.0/powershell.exe"
                ),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        evidence = json.loads(result.stdout)
        self.assertEqual(evidence["nativeDescriptorsChecked"], 12)
        self.assertEqual(evidence["ancestorPoliciesChecked"], 8)
        self.assertFalse(evidence["tasksRegistered"])

    @unittest.skipUnless(
        os.name == "nt", "Actual Windows Task Scheduler COM validation"
    )
    def test_actual_scheduler_validates_without_registering_or_running(self):
        for role in ("core", "web", "caddy"):
            with self.subTest(role=role):
                result = operate(
                    task_plan(self.identifier, r"C:\ProgramData\Kyrion Test", role)
                )
                self.assertTrue(result["definitionValidated"])
                self.assertTrue(result["taskSecurityPolicyValidated"])
                self.assertFalse(result["registered"])
                self.assertFalse(result["coldBootVerified"])
        result = operate(self.plan, "inspect")
        self.assertFalse(result["registered"])
