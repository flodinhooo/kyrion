"""Schema declarations are checked against actual JAR migration entries."""

import runpy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
producer = runpy.run_path(str(ROOT / "release/assemble-windows-profile.py"))


class ProfileSchema(unittest.TestCase):
    def test_actual_jar_schema_is_derived_and_duplicates_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory) / "core.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(
                    "BOOT-INF/classes/db/migration/V48__first.sql", "SELECT 1;"
                )
                archive.writestr(
                    "BOOT-INF/classes/db/migration/V49__next.sql", "SELECT 1;"
                )
            self.assertEqual(producer["core_schema"](jar), 49)
            with zipfile.ZipFile(jar, "a") as archive:
                archive.writestr(
                    "BOOT-INF/classes/db/migration/V49__duplicate.sql", "SELECT 1;"
                )
            with self.assertRaisesRegex(ValueError, "E_NATIVE_CORE_SCHEMA"):
                producer["core_schema"](jar)

    def test_wrong_declared_schema_fails_before_profile_or_vendor_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jar = root / "core.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(
                    "BOOT-INF/classes/db/migration/V49__current.sql", "SELECT 1;"
                )
            with self.assertRaisesRegex(ValueError, "E_NATIVE_PROFILE_SCHEMA"):
                producer["assemble"](
                    root / "vendors", jar, jar, root, root, root / "output", "1.2.3", 48
                )
            self.assertFalse((root / "vendors").exists())
            self.assertFalse((root / "output").exists())
