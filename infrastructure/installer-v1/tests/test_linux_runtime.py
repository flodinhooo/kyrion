"""Real journals; package/systemd/Docker/ownership observations are injected.

These orchestration tests are not OS installation or cold-boot acceptance.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linux_packages as packages
import linux_runtime as setup
import runtime
from bundle import ReviewedBundle
from recovery import load_installation
from runtime import Installation


class LinuxRuntimeTests(unittest.TestCase):
    def test_minimized_documentation_is_not_a_modified_runtime(self):
        self.assertFalse(
            setup.runtime_file_differences(
                "missing     /usr/share/doc/docker.io/README.md\nmissing     /usr/share/lintian/overrides/docker.io\nmissing     /usr/share/man/man8/dockerd.8.gz\n"
            )
        )

    def test_runtime_changes_and_unknown_verification_output_are_rejected(self):
        for text in (
            "missing     /usr/sbin/dockerd",
            "??5?????? /usr/lib/systemd/system/docker.service",
            "missing     /etc/default/docker",
            "missing     /usr/share/doc/../../sbin/dockerd",
            "unrecognized verification output",
        ):
            with self.subTest(text=text):
                self.assertTrue(setup.runtime_file_differences(text))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "installed"
        self.manifest = {
            "release": "1.0.0",
            "architecture": "linux/amd64",
            "artifacts": [{"bytes": 1}],
        }
        self.installation = Installation(
            self.target, self.manifest, "a" * 64, "fixture.test", "10.231.0.1"
        )
        self.enterContext(patch("operational_restore.require_admin"))
        self.enterContext(patch("update_worker.validate_host"))
        self.enterContext(
            patch.object(setup, "preflight", return_value={"architecture": "amd64"})
        )
        self.enterContext(
            patch.object(
                setup,
                "authenticated_review",
                return_value=ReviewedBundle(self.manifest, "a" * 64),
            )
        )
        self.enterContext(patch.object(setup, "image_plan"))
        self.enterContext(patch.object(setup, "systemd_available", return_value=True))
        self.enterContext(patch.object(setup, "has_daemon_state", return_value=False))
        self.enterContext(
            patch.object(setup.shutil, "which", return_value="/usr/bin/docker")
        )
        self.enterContext(patch.object(packages, "supported", return_value=True))
        self.enterContext(
            patch.dict(
                os.environ,
                {key: "" for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG")},
            )
        )
        self.enterContext(patch("update_compose.Compose"))
        self.health = self.enterContext(patch.object(setup, "runtime_checks"))
        self.vendor = self.enterContext(patch.object(setup, "verify_vendor_unit"))
        self.events = []
        self.active, self.enabled, self.stuck = "inactive", "disabled", False
        self.enterContext(patch.object(packages, "run", side_effect=self.command))
        self.package_operation = self.enterContext(
            patch.object(packages, "configure", side_effect=self.install_packages)
        )
        self.review = Mock(side_effect=self.approve)

    def command(self, installation, name, *arguments):
        if name == "docker":
            return "default\n"
        if arguments[:2] == ("show", "docker.service"):
            return f"LoadState=loaded\nActiveState={self.active}\nUnitFileState={self.enabled}\nFragmentPath=/usr/lib/systemd/system/docker.service\nDropInPaths=\n"
        self.events.append((name, arguments))
        if "enable" in arguments:
            self.assertEqual(
                load_installation(self.target).state["linuxRuntimeStartup"]["phase"],
                "configuring",
            )
            if not self.stuck:
                self.active, self.enabled = "active", "enabled"
        return ""

    def approve(self, summary):
        self.events.append(("review", summary["step"]))
        return True

    def install_packages(self, target, **_options):
        installation = load_installation(target)
        self.assertEqual(
            installation.state["linuxRuntimeServiceConsent"],
            {"manifestSha256": "a" * 64, "approved": True},
        )
        self.events.append(("packages", "approved-before-apt"))
        if installation.state.get("runtimePrerequisite"):
            installation.state["runtimePrerequisite"]["phase"] = "complete"
            installation.save()
        return {"available": True, "packagesChanged": True}

    def prepare(self, target=None):
        return setup.prepare(
            target or self.target,
            self.root,
            self.root / "key.pem",
            "a" * 64,
            "fixture.test",
            "10.231.0.1",
            review=self.review,
        )

    def test_service_consent_precedes_apt_and_journal_precedes_start(self):
        result = self.prepare()
        self.assertEqual(
            self.events[:2],
            [("review", "service"), ("packages", "approved-before-apt")],
        )
        self.assertTrue(result["running"])
        self.assertFalse(result["coldBootVerified"])
        state = load_installation(self.target).state
        self.assertEqual(state["stage"], "reviewed")
        self.assertEqual(state["linuxRuntimeStartup"]["phase"], "verified-running")
        self.health.assert_called_once_with("10.231.0.1", "fixture.test", fresh=True)
        self.assertIn("docker-cli", packages.RUNTIME.roots)

    def test_declining_service_consent_never_invokes_apt_or_systemctl_enable(self):
        self.review.side_effect = None
        self.review.return_value = False
        with self.assertRaisesRegex(ValueError, "E_LINUX_RUNTIME_CANCELLED"):
            self.prepare()
        self.package_operation.assert_not_called()
        self.assertEqual(self.events, [])

    def test_service_registration_without_active_daemon_never_reports_readiness(self):
        self.stuck = True
        with self.assertRaisesRegex(ValueError, "E_LINUX_RUNTIME_SERVICE"):
            self.prepare()
        self.health.assert_not_called()
        self.assertEqual(
            load_installation(self.target).state["linuxRuntimeStartup"]["phase"],
            "configuring",
        )

    def test_custom_or_modified_vendor_unit_is_never_started(self):
        self.vendor.side_effect = ValueError("E_LINUX_RUNTIME_CUSTOM_SERVICE")
        with self.assertRaisesRegex(ValueError, "E_LINUX_RUNTIME_CUSTOM_SERVICE"):
            self.prepare()
        self.assertFalse(any(name == "systemctl" for name, _ in self.events))

    def test_changed_consent_cannot_be_reused_for_service_start(self):
        with self.assertRaisesRegex(ValueError, "E_REVIEW_CHANGED"):
            setup.configure_service(
                self.target, review=self.review, approved_manifest="b" * 64
            )
        self.assertEqual(self.events, [])

    def test_unowned_existing_directory_is_not_adopted(self):
        target = self.root / "foreign"
        target.mkdir()
        (target / "foreign.txt").write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "E_EXISTING_STATE"):
            self.prepare(target)
        self.assertEqual((target / "foreign.txt").read_bytes(), b"preserve")
        self.package_operation.assert_not_called()

    def test_unknown_daemon_state_without_cli_is_not_silently_adopted(self):
        with (
            patch.object(setup.shutil, "which", return_value=None),
            patch.object(setup, "has_daemon_state", return_value=True),
            self.assertRaises(ValueError),
        ):
            self.prepare()
        self.package_operation.assert_not_called()

    def test_known_interrupted_own_daemon_install_can_resume_before_cli_exists(self):
        self.installation.state.update(
            {
                "linuxRuntimeOrigin": {
                    "manifestSha256": "a" * 64,
                    "initialDaemonStateEmpty": True,
                },
                "runtimePrerequisite": {
                    "formatVersion": 1,
                    "phase": "installing",
                    "packages": [{"name": "docker.io", "version": "26.1.5"}],
                },
            }
        )
        self.installation.save()
        with (
            patch.object(setup.shutil, "which", return_value=None),
            patch.object(setup, "has_daemon_state", return_value=True),
        ):
            self.assertTrue(self.prepare()["running"])

    def test_remote_or_custom_environment_is_refused_before_package_work(self):
        with (
            patch.dict(os.environ, {"DOCKER_HOST": "tcp://unprepared.invalid:2375"}),
            self.assertRaisesRegex(ValueError, "E_LINUX_RUNTIME_EXISTING"),
        ):
            self.prepare()
        self.package_operation.assert_not_called()
        self.assertEqual(self.events, [])

    def test_owned_reviewed_journal_still_gets_fresh_port_and_foreign_container_checks(
        self,
    ):
        with (
            patch.object(
                runtime,
                "preflight",
                return_value={"architecture": "amd64", "freeBytes": 100 * 1024**3},
            ),
            patch.object(
                runtime,
                "authenticated_review",
                return_value=ReviewedBundle(self.manifest, "a" * 64),
            ),
            patch.object(runtime, "image_plan"),
            patch.object(runtime, "runtime_checks") as checks,
            patch.object(
                runtime,
                "reject_existing_containers",
                side_effect=ValueError("E_EXISTING_STATE"),
            ) as existing,
            self.assertRaisesRegex(ValueError, "E_EXISTING_STATE"),
        ):
            runtime.provision(
                self.target,
                self.root,
                self.root / "key.pem",
                "fixture.test",
                "10.231.0.1",
                "a" * 64,
            )
        checks.assert_called_once_with("10.231.0.1", "fixture.test", fresh=True)
        existing.assert_called_once()
        self.assertEqual(load_installation(self.target).state["stage"], "reviewed")
