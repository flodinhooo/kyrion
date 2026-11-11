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
            with self.assertRaisesRegex(ValueError, "E_PACKAGE"):
                package.build(path)


if __name__ == "__main__":
    unittest.main()
