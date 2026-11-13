"""Archive boundary failures must occur before destructive target operations."""

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portable_database as portable


class PortableDatabase(unittest.TestCase):
    def test_client_file_copy_has_fixed_grammar_and_quotes_literal_paths(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private'rows.copy"
            sql = 'COPY public."account" ("id") FROM STDIN (FORMAT binary)'
            command = portable.file_copy_command(sql, path)
            self.assertIn("private''rows.copy' (FORMAT binary)", command)
            self.assertTrue(command.startswith('\\copy public."account" ("id") FROM '))
            for unsafe in (
                sql + "; SELECT malicious()",
                sql.replace("FROM STDIN", "FROM PROGRAM 'false'"),
                sql.replace('"account"', '"account;drop"'),
            ):
                with self.assertRaises(ValueError):
                    portable.file_copy_command(unsafe, path)

    def setUp(self):
        self.schema = {
            "tables": [
                {"name": "account", "columns": [["id", "uuid", True, "", "", None]]},
                {
                    "name": "flyway_schema_history",
                    "columns": [["version", "text", False, "", "", None]],
                },
            ],
            "sequences": [],
            "foreignKeys": [],
            "migrations": [["49", "synthetic", "SQL", "V49.sql", 123, True]],
        }
        self.snapshot = {
            "formatVersion": 1,
            "schema": copy.deepcopy(self.schema),
            "sequencePositions": {},
        }
        self.query = MagicMock(return_value=json.dumps(self.schema).encode())
        self.execute = MagicMock()
        self.copy = MagicMock()
        self.files = {"database-data/0000.copy": Path("synthetic-never-opened")}

    def refused(self, snapshot, files=None):
        with self.assertRaises(ValueError):
            portable.restore(
                self.query,
                self.execute,
                self.copy,
                snapshot,
                files if files is not None else self.files,
            )
        self.execute.assert_not_called()
        self.copy.assert_not_called()

    def test_unknown_or_sql_bearing_identifiers_are_refused(self):
        for name in (
            "public.account",
            'account";DROP TABLE account;--',
            "../account",
            "Account",
        ):
            value = copy.deepcopy(self.snapshot)
            value["schema"]["tables"][0]["name"] = name
            self.refused(value)

    def test_archived_schema_or_migration_change_is_not_executed(self):
        for path in ("columns", "migrations", "foreignKeys"):
            value = copy.deepcopy(self.snapshot)
            if path == "columns":
                value["schema"]["tables"][0]["columns"][0][1] = "malicious_type"
            elif path == "migrations":
                value["schema"]["migrations"][0][3] = "arbitrary SQL never executed"
            else:
                value["schema"]["foreignKeys"] = [
                    {
                        "table": "account",
                        "name": "synthetic",
                        "definition": "FOREIGN KEY(id) REFERENCES account(id); SELECT malicious()",
                    }
                ]
            self.refused(value)

    def test_missing_extra_or_legacy_data_is_refused_before_truncate(self):
        self.refused(self.snapshot, {})
        self.refused(
            self.snapshot, {**self.files, "database-data/unknown.copy": Path("unknown")}
        )
        self.refused({"formatVersion": 1, "schema": self.schema})

    def test_ambiguous_boolean_version_and_sequence_positions_are_refused(self):
        value = copy.deepcopy(self.snapshot)
        value["formatVersion"] = True
        self.refused(value)
        value = copy.deepcopy(self.snapshot)
        value["sequencePositions"] = {"unexpected": [True, False]}
        self.refused(value)

    def test_signed_target_flyway_history_is_not_overwritten(self):
        portable.restore(self.query, self.execute, self.copy, self.snapshot, self.files)
        commands = [call.args[0] for call in self.execute.call_args_list]
        self.assertTrue(commands[0].startswith('TRUNCATE public."account"'))
        self.assertFalse(any("flyway_schema_history" in sql for sql in commands))
        self.assertEqual(
            self.copy.call_args.args[0],
            'COPY public."account" ("id") FROM STDIN (FORMAT binary)',
        )
