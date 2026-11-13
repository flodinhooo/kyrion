"""Consent/window checks and scheduled orchestration; lifecycle boundaries injected."""

import copy
import datetime as dt
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import update_automatic as automatic
from bundle import sha256
from recovery import allowed_member, load_installation
from runtime import Installation
from update_schedule import linux_plan
from windows_tasks import update_check_plan


def policy():
    return {
        "formatVersion": 1,
        "revision": str(uuid.uuid4()),
        "policyRevision": str(uuid.uuid4()),
        "enabled": True,
        "utcDays": [7],
        "startMinute": 23 * 60 + 30,
        "durationMinutes": 120,
        "maximumDownloadBytes": 1024**3,
        "keySha256": "a" * 64,
    }


class AutomaticUpdates(unittest.TestCase):
    @unittest.skipUnless(
        os.name == "posix" and os.geteuid() == 0,
        "real root-only file mode test; Windows ACL acceptance is separate",
    )
    def test_key_export_and_registration_retry_preserve_same_protected_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "installation"
            installation = Installation(
                root,
                {"release": "1.0.0", "architecture": "linux/amd64"},
                "a" * 64,
                "fixture.test",
                "127.0.0.1",
            )
            executable = Path(temporary) / "synthetic-worker"
            executable.write_bytes(b"test executable identity; never executed")
            worker = "maintenance-" + sha256(executable)[:32]
            installation.write(worker, executable.read_bytes())
            value = policy()
            installation.state["updatePolicy"] = {
                "enabled": True,
                "revision": value["policyRevision"],
                "workerFile": worker,
            }
            installation.save()
            export = Path(temporary) / "backup-recovery.key"
            with (
                patch("operational_restore.require_admin"),
                patch("update_worker.validate_host"),
                patch("update_worker.require_worker"),
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(executable)),
                patch(
                    "update_schedule.operate",
                    side_effect=[
                        {},
                        ValueError("E_UPDATE_SYSTEMD"),
                        {},
                        {"state": "registered"},
                    ],
                ),
            ):
                options = {
                    "days": [1],
                    "start": 60,
                    "duration": 120,
                    "maximum": 1024**3,
                    "export": export,
                    "review": lambda _: True,
                }
                with self.assertRaisesRegex(ValueError, "E_UPDATE_SYSTEMD"):
                    automatic.configure(root, **options)
                before = (root / automatic.KEY).read_bytes()
                approved_revision = load_installation(root).state[
                    "automaticUpdatePolicy"
                ]["revision"]
                outcome = automatic.configure(root, **options)
            self.assertTrue(outcome["enabled"])
            self.assertEqual(outcome["revision"], approved_revision)
            self.assertEqual((root / automatic.KEY).read_bytes(), before)
            self.assertEqual(export.read_bytes(), before)
            self.assertEqual((root / automatic.KEY).stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                (root / ".maintenance-secrets").stat().st_mode & 0o777, 0o700
            )
            self.assertFalse(allowed_member(automatic.KEY))
            self.assertNotIn(
                before.decode().strip(), str(load_installation(root).state)
            )

    def test_window_crosses_midnight_and_week_boundary_with_exclusive_end(self):
        value = policy()
        for instant, expected in (
            ("2026-11-15T23:29:59+00:00", False),
            ("2026-11-15T23:30:00+00:00", True),
            ("2026-11-16T01:29:59+00:00", True),
            ("2026-11-16T01:30:00+00:00", False),
            ("2026-11-16T02:00:00+01:00", True),
        ):
            with self.subTest(instant=instant):
                self.assertEqual(
                    automatic.in_window(value, dt.datetime.fromisoformat(instant)),
                    expected,
                )
        with self.assertRaisesRegex(ValueError, "E_UPDATE_AUTOMATIC_TIME"):
            # Deliberately invalid: naive local time must never imply consent.
            automatic.in_window(value, dt.datetime(2026, 11, 15, tzinfo=None))  # noqa: DTZ001

    def test_invalid_approval_is_rejected(self):
        for field, item in (
            ("enabled", 1),
            ("utcDays", [True]),
            ("utcDays", [1, 1]),
            ("utcDays", []),
            ("startMinute", 1440),
            ("durationMinutes", 59),
            ("maximumDownloadBytes", True),
            ("revision", "invalid"),
            ("keySha256", "path/to/secret"),
        ):
            value = policy()
            value[field] = item
            with self.subTest(field=field), self.assertRaises(ValueError):
                automatic.validate(value)

    def prepare(self):
        value = policy()
        installation = Mock()
        installation.state = {
            "automaticUpdatePolicy": value,
            "updatePolicy": {"enabled": True, "revision": value["policyRevision"]},
        }
        self.enterContext(
            patch.object(
                automatic,
                "installation_lock",
                return_value=__import__("contextlib").nullcontext(),
            )
        )
        self.enterContext(
            patch.object(automatic, "load_installation", return_value=installation)
        )
        self.enterContext(
            patch.object(automatic, "password", return_value="synthetic-key-never-log")
        )
        return installation, value

    def test_manual_transaction_is_never_resumed_automatically(self):
        installation, _value = self.prepare()
        installation.state["updateTransaction"] = {
            "phase": "migrating",
            "actor": "HOST_ADMIN",
        }
        with (
            patch("update_transaction.resume") as resume,
            self.assertRaisesRegex(ValueError, "E_UPDATE_AUTOMATIC_MANUAL"),
        ):
            automatic.run(Path("synthetic"))
        resume.assert_not_called()

    def test_approved_interruption_resumes_without_network_outside_window(self):
        installation, value = self.prepare()
        installation.state["updateTransaction"] = {
            "phase": "activating",
            "actor": "AUTOMATIC",
            "automaticApproval": copy.deepcopy(value),
        }
        with (
            patch.object(automatic, "in_window", return_value=False),
            patch("update_download.download") as download,
            patch(
                "update_transaction.resume", return_value={"complete": True}
            ) as resume,
        ):
            self.assertEqual(automatic.run(Path("synthetic")), {"complete": True})
        download.assert_not_called()
        resume.assert_called_once_with(
            Path("synthetic"), "synthetic-key-never-log", automatic=value
        )

    def test_trust_policy_revision_change_revokes_unattended_approval(self):
        installation, value = self.prepare()
        installation.state["updatePolicy"]["revision"] = str(uuid.uuid4())
        with self.assertRaisesRegex(ValueError, "E_UPDATE_AUTOMATIC_CONSENT"):
            automatic.approved(installation, value, starting=False)

    def test_oversized_download_is_not_approved(self):
        _installation, value = self.prepare()

        def download(_target, *, review):
            self.assertFalse(review({"totalBytes": value["maximumDownloadBytes"] + 1}))
            raise ValueError("E_CONFIRMATION")

        with (
            patch.object(automatic, "in_window", return_value=True),
            patch("update_download.download", side_effect=download),
            patch("update_transaction.apply") as apply,
            self.assertRaisesRegex(ValueError, "E_CONFIRMATION"),
        ):
            automatic.run(Path("synthetic"))
        apply.assert_not_called()

    def test_automatic_schedules_are_finite_hourly_and_manual_remains_daily(self):
        identifier = str(uuid.uuid4())
        worker = "maintenance-" + "a" * 32
        units = linux_plan(identifier, "/var/lib/kyrion", worker, automatic=True)
        self.assertIn(
            "OnUnitActiveSec=1h",
            next(text for name, text in units.items() if name.endswith(".timer")),
        )
        self.assertIn(
            "TimeoutStartSec=2h",
            next(text for name, text in units.items() if name.endswith(".service")),
        )
        plan = update_check_plan(
            identifier, "C:\\ProgramData\\Kyrion", worker + ".exe", automatic=True
        )
        self.assertIn("PT1H", plan["xml"])
        self.assertIn("PT2H", plan["xml"])
        manual = update_check_plan(
            identifier, "C:\\ProgramData\\Kyrion", worker + ".exe"
        )
        self.assertIn("PT24H", manual["xml"])
        self.assertIn("PT10M", manual["xml"])
