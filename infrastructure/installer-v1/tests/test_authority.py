"""Real receipts/private files; service retirement is explicitly injected."""

import copy
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import authority


class Authority(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "secrets").mkdir()
        self.key = b"synthetic-audit-integrity-key-12"
        self.assertEqual(len(self.key), 32)
        (self.root / "secrets/audit-integrity.key").write_bytes(self.key)
        self.source, self.target = str(uuid.uuid4()), str(uuid.uuid4())
        self.state = {"installationId": self.source, "authorityFenceVersion": 1}
        self.saved = []
        self.installation = SimpleNamespace(
            target=self.root,
            state=self.state,
            verify_files=MagicMock(),
            save=lambda: self.saved.append(copy.deepcopy(self.state)),
        )

    def test_receipt_requires_completed_stop_and_is_bound_to_target_and_backup(self):
        def stop(installation):
            self.assertEqual(self.saved[-1]["authority"]["phase"], "retiring")

        receipt = authority.retire(self.installation, self.target, "a" * 64, stop)
        raw = json.dumps(receipt).encode()
        authority.verify_receipt(raw, self.source, self.target, "a" * 64, self.key)
        for target, digest, key in (
            (str(uuid.uuid4()), "a" * 64, self.key),
            (self.target, "b" * 64, self.key),
            (self.target, "a" * 64, b"x" * 32),
        ):
            with self.assertRaises(ValueError):
                authority.verify_receipt(raw, self.source, target, digest, key)
        self.assertEqual(self.saved[-1]["authority"]["phase"], "retired")

    def test_failed_stop_retains_intent_and_same_request_resumes(self):
        stop = MagicMock(side_effect=OSError("synthetic service stop failure"))
        with self.assertRaises(OSError):
            authority.retire(self.installation, self.target, "a" * 64, stop)
        self.assertEqual(self.state["authority"]["phase"], "retiring")
        with self.assertRaisesRegex(ValueError, "E_AUTHORITY_INACTIVE"):
            authority.require_active(self.state)
        stop.side_effect = None
        first = authority.retire(self.installation, self.target, "a" * 64, stop)
        second = authority.retire(self.installation, self.target, "a" * 64, stop)
        self.assertEqual(first, second)
        self.assertEqual(stop.call_count, 3)
        with self.assertRaisesRegex(ValueError, "E_AUTHORITY_TRANSFER_CONFLICT"):
            authority.retire(self.installation, str(uuid.uuid4()), "a" * 64, stop)

    def test_legacy_source_is_not_silently_claimed_fenced(self):
        self.state.pop("authorityFenceVersion")
        stop = MagicMock()
        with self.assertRaisesRegex(ValueError, "E_AUTHORITY_UPGRADE_REQUIRED"):
            authority.retire(self.installation, self.target, "a" * 64, stop)
        stop.assert_not_called()
        self.assertFalse(self.saved)

    def test_export_never_replaces_existing_receipt(self):
        receipt = authority.retire(
            self.installation, self.target, "a" * 64, MagicMock()
        )
        path = self.root / "transfer.json"
        authority.export_receipt(path, receipt)
        self.assertEqual(json.loads(path.read_bytes()), receipt)
        with self.assertRaisesRegex(ValueError, "E_EXISTING_STATE"):
            authority.export_receipt(path, receipt)

    def test_restore_preparation_refuses_existing_data_and_blocks_activation(self):
        self.state.update(stage="services-healthy", files={"secret": "a" * 64})
        with self.assertRaisesRegex(ValueError, "E_RESTORE_TARGET_NOT_EMPTY"):
            authority.prepare_restore(self.installation, {"backupSha256": "a" * 64})
        self.state.update(stage="reviewed", files={})
        authority.prepare_restore(self.installation, {"backupSha256": "a" * 64})
        with self.assertRaisesRegex(ValueError, "E_AUTHORITY_INACTIVE"):
            authority.require_active(self.state)
        authority.require_active(self.state, preparing=True)
        with self.assertRaisesRegex(ValueError, "E_RESTORE_REQUEST_CONFLICT"):
            authority.prepare_restore(self.installation, {"backupSha256": "b" * 64})
