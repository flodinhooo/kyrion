import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import package


class PackageTests(unittest.TestCase):
    def test_archive_node_path_works_without_access_to_checkout_or_packager_module(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kyrion-installer.pyz"
            package.build(path)
            script = """import runpy,sys
from unittest.mock import patch
sys.argv=[sys.argv[1],'--node-heartbeat','--node-config',sys.argv[2]]
with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',return_value='en'):
 runpy.run_path(sys.argv[0],run_name='__main__')
"""
            missing = Path(directory) / "not-created/agent.json"
            result = subprocess.run(
                [sys.executable, "-I", "-c", script, str(path), str(missing)],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            expected = (
                "E_NODE_CONFIG_REQUIRED"
                if sys.platform.startswith("linux")
                else "E_AGENT_PLATFORM"
            )
            self.assertIn(expected, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(missing.parent.exists())

    def test_artifact_contains_only_allowlisted_code_and_assets_and_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kyrion-installer.pyz"
            package.build(path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(
                    set(archive.namelist()), {*package.FILES, "__main__.py"}
                )
            result = subprocess.run(
                [sys.executable, str(path), "--probe"],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            inventory = json.loads(result.stdout)
            self.assertFalse(inventory["platformAccepted"])
            self.assertIn("usableAcceleration", inventory)
            capabilities = subprocess.run(
                [sys.executable, str(path), "--capabilities"],
                capture_output=True,
                text=True,
                timeout=45,
                check=True,
            )
            trust = json.loads(capabilities.stdout)["publicHttpsTrust"]
            self.assertTrue(trust["bundleVerified"])
            self.assertTrue(trust["certificateVerificationRequired"])
            self.assertTrue(trust["hostnameVerificationRequired"])
            self.assertFalse(trust["connectionTested"])
            with self.assertRaisesRegex(ValueError, "E_PACKAGE"):
                package.build(path)


if __name__ == "__main__":
    unittest.main()
