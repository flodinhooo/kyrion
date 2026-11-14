"""Schema growth is a reviewed code change, never supplied by a release feed."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema_support import restore_capability


class SchemaSupport(unittest.TestCase):
    def capability(self, schema):
        return {
            "formatVersion": 1,
            "coreSchema": schema,
            "coreOwnedDisposition": True,
            "recoveryKeyTransfer": True,
        }

    def test_known_legacy_and_current_disposition_contracts_are_accepted(self):
        for schema in (49, 50):
            self.assertEqual(restore_capability(self.capability(schema)), schema)

    def test_future_old_unknown_and_noninteger_schemas_are_refused(self):
        for schema in (48, 51, 1000, True, 49.0, "50", None):
            with (
                self.subTest(schema=schema),
                self.assertRaisesRegex(ValueError, "E_RESTORE_CORE_UPGRADE_REQUIRED"),
            ):
                restore_capability(self.capability(schema))

    def test_schema_number_alone_never_grants_disposition_capability(self):
        for key, value in (
            ("formatVersion", True),
            ("coreOwnedDisposition", 1),
            ("recoveryKeyTransfer", False),
            ("foreign", True),
        ):
            candidate = self.capability(50)
            candidate[key] = value
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(ValueError, "E_RESTORE_CORE_UPGRADE_REQUIRED"),
            ):
                restore_capability(candidate)
