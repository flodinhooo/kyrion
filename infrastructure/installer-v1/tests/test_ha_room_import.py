"""Room import uses existing Core room authority; mock HTTP, no device effects."""

import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from onboarding import CoreError, import_source_room


class RoomImport(unittest.TestCase):
    def test_existing_casefold_match_is_reused(self):
        identity = str(uuid.uuid4())
        client = Mock()
        client.request.return_value = [{"id": identity, "name": " Kitchen "}]
        self.assertEqual(import_source_room(client, "kitchen"), identity)
        client.request.assert_called_once_with("GET", "/v1/home/rooms")

    def test_new_room_uses_core_and_default_other_type(self):
        identity = str(uuid.uuid4())
        client = Mock()
        client.request.side_effect = [[], {"id": identity}]
        self.assertEqual(import_source_room(client, "Fixture room"), identity)
        self.assertEqual(
            client.request.call_args.args,
            ("POST", "/v1/home/rooms", {"name": "Fixture room", "roomType": "other"}),
        )

    def test_concurrent_creation_is_reread_without_second_write(self):
        identity = str(uuid.uuid4())
        client = Mock()
        client.request.side_effect = [
            [],
            CoreError("ROOM_CONFLICT", 409),
            [{"id": identity, "name": "Fixture"}],
        ]
        self.assertEqual(import_source_room(client, "Fixture"), identity)
        self.assertEqual(
            sum(call.args[0] == "POST" for call in client.request.call_args_list), 1
        )

    def test_permission_denial_is_not_retried_or_overridden(self):
        client = Mock()
        client.request.side_effect = [[], CoreError("FORBIDDEN", 403)]
        with self.assertRaisesRegex(CoreError, "FORBIDDEN"):
            import_source_room(client, "Fixture")
        self.assertEqual(client.request.call_count, 2)

    def test_ambiguous_names_never_create_another_room(self):
        client = Mock()
        client.request.return_value = [
            {"id": str(uuid.uuid4()), "name": "Kitchen"},
            {"id": str(uuid.uuid4()), "name": "kitchen"},
        ]
        with self.assertRaisesRegex(ValueError, "E_HA_ROOM_AMBIGUOUS"):
            import_source_room(client, "kitchen")
        client.request.assert_called_once()

    def test_invalid_provider_area_cannot_trigger_http(self):
        for name in ("", "x" * 121, "room\nname", "room\x1b[2J"):
            client = Mock()
            with self.assertRaisesRegex(ValueError, "E_HA_SOURCE_ROOM"):
                import_source_room(client, name)
            client.request.assert_not_called()
