"""Offline rejection tests; integration/recovery cases run in the Core rehearsal."""

import argparse
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "schema_tool", Path(__file__).with_name("Migrate-CoreSchema.py")
)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class SchemaToolTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.jar = self.root / "core.jar"
        self.extract = self.root / "extract"
        (self.extract / "sql").mkdir(parents=True)
        (self.extract / "lib").mkdir()

    def artifact(self, versions=range(1, 46), extra=None):
        with zipfile.ZipFile(self.jar, "w") as archive:
            for version in versions:
                archive.writestr(
                    f"BOOT-INF/classes/db/migration/V{version}__synthetic.sql",
                    f"-- {version}\n",
                )
            for name in (
                "flyway-core-12.4.0.jar",
                "flyway-database-postgresql-12.4.0.jar",
                "postgresql-42.7.11.jar",
            ):
                archive.writestr("BOOT-INF/lib/" + name, b"synthetic")
            archive.writestr(
                "BOOT-INF/classes/dev/kyrion/core/Untrusted.class", b"never extracted"
            )
            archive.writestr("BOOT-INF/lib/spring-boot-4.1.0.jar", b"never extracted")
            if extra:
                archive.writestr(*extra)
        return hashlib.sha256(self.jar.read_bytes()).hexdigest()

    def test_extracts_only_reviewed_catalog_and_allowlisted_libraries(self):
        catalog = TOOL.extract_artifact(self.jar, self.artifact(), self.extract)
        self.assertEqual(45, len(catalog["migrations"]))
        self.assertEqual(48, sum(path.is_file() for path in self.extract.rglob("*")))

    def test_accepts_combined_v46_catalog(self):
        catalog = TOOL.extract_artifact(
            self.jar, self.artifact(range(1, 47)), self.extract
        )
        self.assertEqual(46, len(catalog["migrations"]))

    def test_accepts_selected_recipient_v47_catalog(self):
        catalog = TOOL.extract_artifact(
            self.jar, self.artifact(range(1, 48)), self.extract
        )
        self.assertEqual(47, len(catalog["migrations"]))

    def test_rejects_wrong_hash_before_extraction(self):
        self.artifact()
        with self.assertRaisesRegex(ValueError, "ARTIFACT_HASH_MISMATCH"):
            TOOL.extract_artifact(self.jar, "0" * 64, self.extract)
        self.assertEqual([], list((self.extract / "sql").iterdir()))

    def test_rejects_missing_migrations(self):
        with self.assertRaisesRegex(
            ValueError, "ARTIFACT_CATALOG_NOT_V1_TO_V45_V46_OR_V47"
        ):
            TOOL.extract_artifact(self.jar, self.artifact(range(1, 45)), self.extract)

    def test_rejects_future_migration(self):
        with self.assertRaisesRegex(
            ValueError, "ARTIFACT_CATALOG_NOT_V1_TO_V45_V46_OR_V47"
        ):
            TOOL.extract_artifact(self.jar, self.artifact(range(1, 49)), self.extract)

    def test_rejects_callback_or_path_traversal(self):
        for name in ("beforeMigrate.sql", "../../escape.sql"):
            with self.assertRaisesRegex(ValueError, "ARTIFACT_UNEXPECTED_MIGRATION"):
                TOOL.extract_artifact(
                    self.jar,
                    self.artifact(
                        extra=("BOOT-INF/classes/db/migration/" + name, b"select 1")
                    ),
                    self.extract,
                )

    def test_rejects_duplicate_version(self):
        with self.assertRaisesRegex(ValueError, "ARTIFACT_DUPLICATE_VERSION"):
            TOOL.extract_artifact(
                self.jar,
                self.artifact(
                    extra=("BOOT-INF/classes/db/migration/V45__other.sql", b"select 1")
                ),
                self.extract,
            )

    def test_rejects_nested_library_path(self):
        with self.assertRaisesRegex(ValueError, "ARTIFACT_LIBRARY_PATH_INVALID"):
            TOOL.extract_artifact(
                self.jar,
                self.artifact(
                    extra=("BOOT-INF/lib/nested/flyway-core-12.4.0.jar", b"invalid")
                ),
                self.extract,
            )

    def arguments(self):
        connection = self.root / "connection.json"
        connection.write_text(
            json.dumps(
                {
                    "host": "127.0.0.1",
                    "port": 5432,
                    "database": "synthetic",
                    "user": "test",
                    "password": "never-log-this",
                    "sslmode": "disable",
                }
            ),
            encoding="utf-8",
        )
        return argparse.Namespace(
            connection_file=connection,
            apply=True,
            approve_plan_sha256=None,
            expected_target=None,
            plan=self.root / "plan.json",
            artifact=self.jar,
            artifact_sha256="0" * 64,
            java_home=None,
            target_version=45,
        )

    def test_apply_requires_explicit_plan_approval(self):
        with patch.object(TOOL.subprocess, "run") as child:
            with self.assertRaisesRegex(ValueError, "APPLY_APPROVAL_REQUIRED"):
                TOOL.run(self.arguments())
            child.assert_not_called()

    def test_apply_rejects_tampered_plan(self):
        args = self.arguments()
        args.approve_plan_sha256 = "0" * 64
        args.expected_target = "1" * 64
        args.plan.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "PLAN_HASH_MISMATCH"):
            TOOL.run(args)

    def test_apply_rejects_artifact_or_target_mismatch(self):
        args = self.arguments()
        args.expected_target = "1" * 64
        for document, error in (
            ({"artifactSha256": "2" * 64}, "PLAN_ARTIFACT_MISMATCH"),
            (
                {"artifactSha256": "0" * 64, "state": {"targetIdentity": "2" * 64}},
                "PLAN_TARGET_MISMATCH",
            ),
        ):
            args.plan.write_text(
                json.dumps({"format": "kyrion-schema-plan-v1", **document}),
                encoding="utf-8",
            )
            args.approve_plan_sha256 = hashlib.sha256(
                args.plan.read_bytes()
            ).hexdigest()
            with self.assertRaisesRegex(ValueError, error):
                TOOL.run(args)

    def test_remote_plaintext_is_rejected_before_any_connection(self):
        args = self.arguments()
        data = json.loads(args.connection_file.read_text())
        data["host"] = "remote.invalid"
        args.connection_file.write_text(json.dumps(data), encoding="utf-8")
        with patch.object(TOOL.subprocess, "run") as child:
            with self.assertRaisesRegex(ValueError, "CONNECTION_TLS_REQUIRED"):
                TOOL.run(args)
            child.assert_not_called()

    def test_plan_target_version_cannot_change_on_apply(self):
        args = self.arguments()
        args.java_home = self.root
        args.expected_target = "1" * 64
        args.plan.write_text(
            json.dumps(
                {
                    "format": "kyrion-schema-plan-v1",
                    "artifactSha256": args.artifact_sha256,
                    "state": {"targetIdentity": args.expected_target},
                    "targetVersion": 46,
                }
            ),
            encoding="utf-8",
        )
        args.approve_plan_sha256 = hashlib.sha256(args.plan.read_bytes()).hexdigest()
        with patch.object(TOOL.subprocess, "run") as child:
            child.return_value.returncode = 0
            child.return_value.stderr = b'openjdk version "21.0.13"'
            with self.assertRaisesRegex(ValueError, "PLAN_TARGET_VERSION_MISMATCH"):
                TOOL.run(args)
            child.assert_called_once()  # Java version only; no compiler or database.


if __name__ == "__main__":
    unittest.main()
