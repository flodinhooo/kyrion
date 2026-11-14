"""Real installer journals; APT/dpkg/privilege observations are injected."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linux_crypto as crypto
import linux_packages as package_ops
from recovery import load_installation
from runtime import Installation


class LinuxCryptoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name) / "installed"
        self.installation = Installation(
            self.target,
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.enterContext(patch("operational_restore.require_admin"))
        self.enterContext(patch("update_worker.validate_host"))
        self.enterContext(patch.object(package_ops, "supported", return_value=True))
        self.available = self.enterContext(
            patch.object(crypto, "available", side_effect=[False, True])
        )
        self.enterContext(
            patch.object(
                package_ops.shutil,
                "disk_usage",
                return_value=SimpleNamespace(free=100 * 1024**3),
            )
        )
        self.calls = []
        self.unfinished = ""
        self.interrupt = False
        self.solver = "Inst gnupg (2.4.7-21 Debian:13/stable [all])\nInst gpgconf (2.4.7-21 Debian:13/stable [amd64])\n"
        self.enterContext(patch.object(package_ops, "run", side_effect=self.execute))
        self.review = Mock(return_value=True)

    def execute(self, installation, name, *arguments):
        self.calls.append((name, arguments))
        if name == "dpkg-query":
            return "base-files\tinstalled\n" + self.unfinished
        if name == "apt-cache":
            package, version = arguments[-1].split("=")
            return f"Package: {package}\nVersion: {version}\nSize: 1024\nInstalled-Size: 2\n"
        if "--simulate" in arguments:
            return self.solver
        if self.interrupt and "--no-download" in arguments:
            raise ValueError("E_CRYPTO_PACKAGE_INTERRUPTED")
        return ""

    def configure(self):
        return crypto.configure(self.target, review=self.review)

    def test_reviewed_pinned_download_install_and_real_journal(self):
        self.assertTrue(self.configure()["available"])
        state = load_installation(self.target).state["cryptoPrerequisite"]
        self.assertEqual(state["phase"], "complete")
        self.assertEqual(self.review.call_count, 2)
        self.assertEqual(self.review.call_args.args[0]["maximumDownloadBytes"], 2048)
        final = next(args for _, args in self.calls if "--no-download" in args)
        self.assertIn("gnupg=2.4.7-21", final)
        self.assertIn("--no-remove", final)
        self.assertIn("APT::Get::AllowUnauthenticated=false", final)
        self.assertNotIn("--fix-broken", final)

    def test_declining_metadata_performs_no_package_mutation(self):
        self.review.return_value = False
        self.assertTrue(self.configure()["cancelled"])
        self.assertTrue(all(name == "dpkg-query" for name, _ in self.calls))
        self.assertNotIn("cryptoPrerequisite", load_installation(self.target).state)

    def test_declining_install_only_refreshes_approved_metadata(self):
        self.review.side_effect = [True, False]
        self.assertTrue(self.configure()["cancelled"])
        self.assertEqual(
            load_installation(self.target).state["cryptoPrerequisite"]["phase"],
            "metadata",
        )
        self.assertFalse(any("--yes" in args for _, args in self.calls))

    def test_unrelated_pending_packages_never_receive_global_repair(self):
        self.unfinished = "foreign-package\tunpacked\n"
        with self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_REPAIR"):
            self.configure()
        self.review.assert_not_called()
        self.assertFalse(any(name in {"apt-get", "dpkg"} for name, _ in self.calls))

    def test_interrupted_install_resumes_only_its_reviewed_pending_packages(self):
        self.interrupt = True
        with self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_INTERRUPTED"):
            self.configure()
        self.assertEqual(
            load_installation(self.target).state["cryptoPrerequisite"]["phase"],
            "installing",
        )
        self.interrupt = False
        self.unfinished = "gnupg\tunpacked\n"
        self.assertTrue(self.configure()["available"])
        self.assertIn(("dpkg", ("--configure", "gnupg")), self.calls)
        self.assertFalse(any("--pending" in args for _, args in self.calls))
        self.assertEqual(self.review.call_count, 2)

    def test_recovery_refuses_unrelated_pending_work(self):
        self.interrupt = True
        with self.assertRaises(ValueError):
            self.configure()
        self.unfinished = "foreign-package\tunpacked\n"
        with self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_REPAIR"):
            self.configure()
        self.assertFalse(any(name == "dpkg" for name, _ in self.calls))

    def test_existing_tools_are_reused_without_metadata_or_package_changes(self):
        self.available.side_effect = None
        self.available.return_value = True
        self.assertFalse(self.configure()["packagesChanged"])
        self.assertEqual(self.calls, [])
        self.review.assert_not_called()

    def test_metadata_only_intent_can_close_when_tools_were_supplied_elsewhere(self):
        self.installation.state["cryptoPrerequisite"] = {
            "formatVersion": 1,
            "phase": "metadata",
            "packages": [],
        }
        self.installation.save()
        self.available.side_effect = None
        self.available.return_value = True
        self.assertFalse(self.configure()["packagesChanged"])
        self.assertNotIn("cryptoPrerequisite", load_installation(self.target).state)
        self.assertEqual(self.calls, [])

    def test_another_owned_active_package_intent_is_not_overlapped(self):
        self.installation.state["runtimePrerequisite"] = {
            "formatVersion": 1,
            "phase": "installing",
            "packages": [{"name": "docker.io", "version": "26.1.5"}],
        }
        self.installation.save()
        with self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_REPAIR"):
            self.configure()
        self.assertEqual(self.calls, [])
        self.review.assert_not_called()

    def test_package_exit_success_is_not_tool_readiness(self):
        self.available.side_effect = None
        self.available.return_value = False
        with self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_TOOL"):
            self.configure()
        self.assertEqual(
            load_installation(self.target).state["cryptoPrerequisite"]["phase"],
            "installing",
        )

    def test_solver_cannot_add_an_unreviewed_dependency_after_consent(self):
        def review(summary):
            if summary["step"] == "install":
                self.solver += "Inst unreviewed (1.0 Debian [all])\n"
            return True

        self.review.side_effect = review
        with self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_PLAN"):
            self.configure()
        self.assertFalse(any("--yes" in args for _, args in self.calls))

    def test_incomplete_own_intent_is_not_skipped_when_tools_already_exist(self):
        self.interrupt = True
        with self.assertRaises(ValueError):
            self.configure()
        self.interrupt = False
        self.available.side_effect = None
        self.available.return_value = True
        self.unfinished = "gnupg\tunpacked\n"
        self.assertTrue(self.configure()["packagesChanged"])
        self.assertIn(("dpkg", ("--configure", "gnupg")), self.calls)

    def test_update_or_retirement_fences_precede_package_probe(self):
        for state in (
            {"preparedForRestore": True},
            {"updateTransaction": {"phase": "migrating"}},
        ):
            with self.subTest(state=state):
                self.installation.state.update(state)
                self.installation.save()
                with self.assertRaises(ValueError):
                    self.configure()
                self.available.assert_not_called()
                self.assertEqual(self.calls, [])
                for key in state:
                    self.installation.state.pop(key)

    def test_removals_upgrades_malformed_or_duplicate_plans_fail_closed(self):
        for raw in (
            "Remv foreign [1.0]\n",
            "Inst foreign [1.0] (2.0 Debian [amd64])\n",
            "Inst --unsafe (1 Debian)\n",
            self.solver * 2,
        ):
            with (
                self.subTest(raw=raw),
                self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_PLAN"),
            ):
                crypto.plan_rows(raw)

    def test_saved_plan_cannot_reinterpret_approved_packages_as_unapproved_metadata(
        self,
    ):
        for phase, packages in (
            ("metadata", [{"name": "gnupg", "version": "2.4.7"}]),
            ("planned", [{"name": "unrelated", "version": "1.0"}]),
        ):
            with (
                self.subTest(phase=phase),
                self.assertRaisesRegex(ValueError, "E_CRYPTO_PACKAGE_PLAN"),
            ):
                crypto.validate(
                    {"formatVersion": 1, "phase": phase, "packages": packages}
                )
