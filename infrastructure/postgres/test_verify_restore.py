"""Restore-target guards: synthetic files and a fake Docker command only."""

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SHELL = shutil.which("pwsh") or shutil.which("powershell.exe")
SCRIPT = Path(__file__).with_name("verify-restore.ps1")


@unittest.skipUnless(SHELL, "PowerShell is required for this operator-tool test")
class RestoreTargetGuardTest(unittest.TestCase):
    def probe(self, target, *, manifest=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = root / "synthetic.dump"
            backup.write_bytes(b"synthetic fixture, not personal data")
            if manifest:
                backup.with_suffix(".dump.json").write_text(
                    json.dumps(
                        {
                            "format": "kyrion-postgresql-backup",
                            "formatVersion": 1,
                            "sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                        }
                    )
                )
            inspect = root / "inspect.json"
            inspect.write_text(json.dumps([target]))
            marker = root / "mutation-attempted"
            wrapper = root / "probe.ps1"
            wrapper.write_text(
                "param($Script,$Backup,$Inspect,$Marker)\n"
                "$global:inspection = Get-Content -Raw -LiteralPath $Inspect\n"
                "$global:markerPath = $Marker\n"
                "function global:docker {\n"
                "  if ($args[0] -eq 'inspect') { $global:LASTEXITCODE=0; "
                "Write-Output $global:inspection; return }\n"
                "  Set-Content -LiteralPath $global:markerPath -Value 'attempted'\n"
                "  throw 'SYNTHETIC_MUTATION_BOUNDARY'\n"
                "}\n"
                "& $Script -Backup $Backup -Container 'synthetic-fixture'\n"
            )
            result = subprocess.run(
                [
                    SHELL,
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(wrapper),
                    str(SCRIPT),
                    str(backup),
                    str(inspect),
                    str(marker),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return result.stdout + result.stderr, marker.exists()

    @staticmethod
    def isolated():
        return {
            "Id": "a" * 64,
            "Config": {"Labels": {"io.kyrion.restore-target": "true"}},
            "HostConfig": {
                "NetworkMode": "none",
                "PortBindings": {},
                "Tmpfs": {"/var/lib/postgresql/data": ""},
            },
            # Docker can report tmpfs only in HostConfig and leave Mounts empty.
            "Mounts": [],
            "State": {"Running": True},
        }

    def test_missing_manifest_stops_before_any_mutation(self):
        output, mutated = self.probe(self.isolated(), manifest=False)
        self.assertIn("BACKUP_MANIFEST_REQUIRED", output)
        self.assertFalse(mutated)

    def test_personal_networked_persistent_or_unmarked_targets_are_rejected(self):
        cases = []
        for change in [
            "unmarked",
            "network",
            "published",
            "persistent",
            "no_tmpfs",
            "stopped",
        ]:
            target = copy.deepcopy(self.isolated())
            if change == "unmarked":
                target["Config"]["Labels"] = {}
            elif change == "network":
                target["HostConfig"]["NetworkMode"] = "bridge"
            elif change == "published":
                target["HostConfig"]["PortBindings"] = {
                    "5432/tcp": [{"HostPort": "5432"}]
                }
            elif change == "persistent":
                target["Mounts"] = [{"Type": "bind"}]
            elif change == "no_tmpfs":
                target["HostConfig"]["Tmpfs"] = {}
            elif change == "stopped":
                target["State"]["Running"] = False
            cases.append((change, target))
        for name, target in cases:
            with self.subTest(name=name):
                output, mutated = self.probe(target)
                self.assertIn("ISOLATED_RESTORE_TARGET_REQUIRED", output)
                self.assertFalse(mutated)

    def test_marked_truly_isolated_target_reaches_restore_boundary(self):
        output, mutated = self.probe(self.isolated())
        self.assertNotIn("ISOLATED_RESTORE_TARGET_REQUIRED", output)
        self.assertIn("SYNTHETIC_MUTATION_BOUNDARY", output)
        self.assertTrue(mutated)


if __name__ == "__main__":
    unittest.main()
