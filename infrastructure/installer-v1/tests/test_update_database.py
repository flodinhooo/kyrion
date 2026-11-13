"""SQL boundary tests; real PostgreSQL interruption checks live in integration/."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_database as database


class UpdateDatabaseRecovery(unittest.TestCase):
    def test_resumed_completed_rename_reasserts_failed_database_isolation(self):
        value = {
            "id": "8d47a930-041e-43fc-b809-72388323b47e",
            "databaseRenameIntent": True,
        }
        platform = Mock()
        installation = SimpleNamespace(state={"updateTransaction": value})
        with (
            patch.object(database, "exists", return_value=True),
            patch.object(
                database,
                "marker",
                side_effect=[
                    "kyrion-update:" + value["id"] + ":snapshot",
                    "kyrion-update:" + value["id"] + ":recovery",
                ],
            ),
        ):
            database.recover(platform, installation, {})
        commands = [entry.args[0] for entry in platform.query.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertIn("pg_terminate_backend", commands[0])
        self.assertEqual(
            commands[1],
            'ALTER DATABASE "kyrion_failed_8d47a930041e43fcb80972388323b47e" ALLOW_CONNECTIONS false',
        )

    def test_foreign_database_is_not_mutated_without_durable_rename_intent(self):
        platform = Mock()
        with (
            patch.object(database, "exists", return_value=True),
            self.assertRaisesRegex(ValueError, "E_UPDATE_DATABASE_FOREIGN"),
        ):
            database.lock_failed(platform, {}, "kyrion_failed_" + "a" * 32)
        platform.query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
