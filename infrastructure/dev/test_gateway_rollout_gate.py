"""V42/V43 rollback gate checks with synthetic JARs; never queries Docker or live SQL."""

import importlib.util
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "gateway_runtime_gate", Path(__file__).with_name("Verify-CoreRuntime.py")
)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class GatewayRolloutGateTest(unittest.TestCase):
    def verify(self, artifact_version, installed_version, leases=0):
        sql = "SELECT 1;"
        checksum = zlib.crc32(sql.encode())
        if checksum >= 2**31:
            checksum -= 2**32
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "synthetic.jar"
            with zipfile.ZipFile(artifact, "w") as archive:
                for version in range(1, artifact_version + 1):
                    archive.writestr(
                        f"BOOT-INF/classes/db/migration/V{version}__synthetic.sql", sql
                    )

            def query(statement):
                if "flyway_schema_history" in statement:
                    return "\n".join(
                        f"{version}|{checksum}|t"
                        for version in range(1, installed_version + 1)
                    )
                self.assertIn("calendar_sync_schedule", statement)
                return str(leases)

            with patch.object(GATE, "query", side_effect=query):
                return GATE.verify(artifact)

    def test_v41_binary_is_refused_after_v43(self):
        result = self.verify(41, 43)
        self.assertFalse(result["safe"])
        self.assertEqual(["42", "43"], result["mismatchedVersions"])

    def test_v43_candidate_is_refused_before_migration(self):
        result = self.verify(43, 41)
        self.assertFalse(result["safe"])
        self.assertEqual(["42", "43"], result["pendingVersions"])

    def test_matching_history_and_quiet_leases_pass(self):
        self.assertTrue(self.verify(43, 43)["safe"])

    def test_matching_history_is_insufficient_with_live_lease(self):
        self.assertFalse(self.verify(43, 43, leases=1)["safe"])

    def test_home03_migration_cannot_be_silently_added_to_v43_release(self):
        result = self.verify(44, 43)
        self.assertFalse(result["safe"])
        self.assertEqual(["44"], result["pendingVersions"])

    def test_v43_fallback_cannot_ignore_installed_home03_schema(self):
        result = self.verify(43, 44)
        self.assertFalse(result["safe"])
        self.assertEqual(["44"], result["mismatchedVersions"])


if __name__ == "__main__":
    unittest.main()
