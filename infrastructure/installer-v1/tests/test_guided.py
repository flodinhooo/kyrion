"""Synthetic files/runtime responses; these do not certify any host installation."""

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle
import host
import runtime


def fixture(root: Path) -> dict:
    artifact = root / "image.tar"
    artifact.write_bytes(b"fixture")
    manifest = {
        "schemaVersion": 1,
        "release": "1.2.3",
        "architecture": "linux/arm64",
        "artifacts": [
            {
                "name": "image.tar",
                "bytes": 7,
                "sha256": hashlib.sha256(b"fixture").hexdigest(),
            }
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


class ManifestTests(unittest.TestCase):
    def test_unsafe_or_duplicate_names_and_typed_sizes_are_rejected(self):
        for field, value in (
            ("name", "../image.tar"),
            ("name", "/image.tar"),
            ("name", "a\\image.tar"),
            ("bytes", True),
            ("bytes", -1),
            ("bytes", "7"),
            ("sha256", "x" * 64),
        ):
            with (
                self.subTest(field=field, value=value),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                manifest = fixture(root)
                manifest["artifacts"][0][field] = value
                (root / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    bundle.validate(root, root / "manifest.json")

    def test_duplicate_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = fixture(root)
            manifest["artifacts"] *= 2
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                bundle.validate(root, root / "manifest.json")

    def test_duplicate_json_fields(self):
        with self.assertRaises(ValueError):
            json.loads(
                '{"release":"1.0.0","release":"2.0.0"}',
                object_pairs_hook=bundle.unique_object,
            )

    def test_non_object_fields(self):
        for value in ([], None, True, {"schemaVersion": True}):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "manifest.json").write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    bundle.validate(root, root / "manifest.json")

    def test_symlink_is_not_hidden_by_resolve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "image.tar").rename(root / "real.tar")
            try:
                (root / "image.tar").symlink_to(root / "real.tar")
            except OSError:
                self.skipTest("Host does not permit fixture symlinks")
            with self.assertRaises(ValueError):
                bundle.validate(root, root / "manifest.json")

    def test_invalid_signature_stops_before_digest_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "manifest.sig").write_bytes(b"bad")
            (root / "public.pem").write_bytes(b"not a public key")
            with (
                patch(
                    "bundle.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 1),
                ),
                patch("bundle.validate") as validate,
            ):
                with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
                    bundle.authenticate(root, root / "public.pem")
                validate.assert_not_called()

    @unittest.skipUnless(
        shutil.which("openssl"),
        "OpenSSL executable required for real signature verification",
    )
    def test_real_ed25519_signature_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            for arguments in (
                ["genpkey", "-algorithm", "ED25519", "-out", str(root / "private.pem")],
                [
                    "pkey",
                    "-in",
                    str(root / "private.pem"),
                    "-pubout",
                    "-out",
                    str(root / "public.pem"),
                ],
                [
                    "pkeyutl",
                    "-sign",
                    "-rawin",
                    "-inkey",
                    str(root / "private.pem"),
                    "-in",
                    str(root / "manifest.json"),
                    "-out",
                    str(root / "manifest.sig"),
                ],
            ):
                subprocess.run(
                    ["openssl", *arguments], capture_output=True, check=True, timeout=10
                )
            self.assertEqual(
                bundle.authenticate(root, root / "public.pem")["release"], "1.2.3"
            )
            (root / "manifest.json").write_text(
                (root / "manifest.json").read_text().replace("1.2.3", "1.2.4")
            )
            with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
                bundle.authenticate(root, root / "public.pem")

    def test_only_expected_four_images_can_be_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = fixture(Path(directory))
            with self.assertRaisesRegex(ValueError, "E_ARTIFACTS"):
                runtime.image_plan(manifest)

    def test_exact_image_tag_and_config_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.tar"
            config = b'{"architecture":"arm64","os":"linux"}'
            with tarfile.open(path, "w") as archive:
                for name, value in (
                    (
                        "manifest.json",
                        json.dumps(
                            [
                                {
                                    "Config": "config.json",
                                    "RepoTags": ["kyrion/core:1.2.3"],
                                }
                            ]
                        ).encode(),
                    ),
                    ("config.json", config),
                ):
                    info = tarfile.TarInfo(name)
                    info.size = len(value)
                    archive.addfile(info, io.BytesIO(value))
            self.assertEqual(
                runtime.image_identity(path, "kyrion/core:1.2.3"),
                "sha256:" + hashlib.sha256(config).hexdigest(),
            )
            with self.assertRaisesRegex(ValueError, "E_IMAGE"):
                runtime.image_identity(path, "foreign/core:1.2.3")


class HostTests(unittest.TestCase):
    def test_platform_candidate_matrix_and_unknown_hardware(self):
        for system, distro, version, machine, allowed in (
            ("Linux", "debian", "13", "x86_64", True),
            ("Linux", "raspbian", "13", "aarch64", True),
            ("Linux", "debian", "12", "aarch64", False),
            ("Linux", "ubuntu", "24.04", "x86_64", False),
            ("Linux", "debian", "13", "armv7l", False),
            ("Windows", "", "", "AMD64", False),
        ):
            with (
                self.subTest(
                    system=system, distro=distro, version=version, machine=machine
                ),
                patch("host.platform.system", return_value=system),
                patch("host.platform.machine", return_value=machine),
                patch(
                    "host.linux_release",
                    return_value={"ID": distro, "VERSION_ID": version},
                ),
                patch("host.command", return_value=None),
            ):
                observed = host.inventory(Path(tempfile.gettempdir()))
                self.assertEqual(observed["candidateProvisioning"], allowed)
                self.assertIsNone(observed["gpuVendorObservation"])
                self.assertIsNone(observed["usableAcceleration"])
                self.assertIsNone(observed["hardwareOwnership"])
                self.assertFalse(observed["platformAccepted"])

    def test_remote_docker_context_refused(self):
        responses = [
            "2.30.0",
            '{"OSType":"linux"}',
            '[{"Endpoints":{"docker":{"Host":"tcp://192.168.1.4:2375"}}}]',
        ]
        with (
            patch("host.command", side_effect=responses),
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(ValueError, "E_DOCKER"),
        ):
            host.runtime_checks("192.168.1.2", "kyrion.home.arpa")

    def test_login_startup_is_not_accepted_as_system_startup(self):
        responses = [
            "2.30.0",
            '{"OSType":"linux"}',
            '[{"Endpoints":{"docker":{"Host":"unix:///var/run/docker.sock"}}}]',
            "active",
            "disabled",
        ]
        with (
            patch("host.command", side_effect=responses),
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(ValueError, "E_AUTOSTART"),
        ):
            host.runtime_checks("192.168.1.2", "kyrion.home.arpa")


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.target = Path(self.temporary.name) / "install"
        self.manifest = {"release": "1.2.3", "architecture": "linux/arm64"}

    def create(self, digest="a" * 64):
        return runtime.Installation(
            self.target, self.manifest, digest, "kyrion.home.arpa", "192.168.1.2"
        )

    def test_resume_does_not_change_secret(self):
        installation = self.create()
        installation.write("secrets/test.key", b"a" * 32)
        resumed = self.create()
        resumed.write("secrets/test.key", b"b" * 32)
        self.assertEqual((self.target / "secrets/test.key").read_bytes(), b"a" * 32)
        self.assertEqual(
            resumed.state["installationId"], installation.state["installationId"]
        )

    def test_different_release_cannot_resume(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "E_RESUME"):
            self.create("b" * 64)

    def test_copied_installation_is_not_silently_adopted(self):
        self.create()
        clone = self.target.parent / "copied-installation"
        shutil.copytree(self.target, clone)
        with self.assertRaisesRegex(ValueError, "E_INSTALLATION_LOCATION"):
            runtime.Installation(
                clone, self.manifest, "a" * 64, "kyrion.home.arpa", "192.168.1.2"
            )

    def test_no_secret_content_in_journal(self):
        installation = self.create()
        installation.write("secrets/test.key", b"synthetic-private-secret")
        self.assertNotIn("synthetic-private-secret", installation.path.read_text())

    @unittest.skipUnless(
        shutil.which("openssl"), "OpenSSL required for actual TLS generation"
    )
    def test_configuration_generates_real_tls_and_raw_keys_without_rotation(self):
        installation = self.create()
        with patch("runtime.os.chown", create=True):
            installation.configure()
            before = dict(installation.state["files"])
            installation.configure()
        self.assertEqual(installation.state["files"], before)
        self.assertEqual(len((self.target / "secrets/credential.key").read_bytes()), 32)
        self.assertEqual(
            len((self.target / "secrets/audit-integrity.key").read_bytes()), 32
        )
        certificate = self.target / "data/tls/cert.pem"
        result = subprocess.run(
            [
                "openssl",
                "x509",
                "-in",
                str(certificate),
                "-noout",
                "-ext",
                "subjectAltName",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        self.assertIn("kyrion.home.arpa", result.stdout)
        self.assertIn("192.168.1.2", result.stdout)

    def test_concurrent_installer_is_refused_and_lock_released(self):
        with runtime.installation_lock(self.target):  # noqa: SIM117 -- hold first lock while acquiring second
            with (
                self.assertRaisesRegex(ValueError, "E_LOCKED"),
                runtime.installation_lock(self.target),
            ):
                self.fail("lock should not be acquired")
        with runtime.installation_lock(self.target):
            pass

    def test_other_process_cannot_enter_held_installation_lock(self):
        script = """import sys
from pathlib import Path
from runtime import installation_lock
try:
 with installation_lock(Path(sys.argv[1])): pass
except ValueError as error:
 sys.exit(23 if str(error).startswith('E_LOCKED') else 24)
sys.exit(0)
"""
        with runtime.installation_lock(self.target):
            result = subprocess.run(
                [sys.executable, "-c", script, str(self.target)],
                cwd=Path(runtime.__file__).parent,
                capture_output=True,
                timeout=10,
                check=False,
            )
        self.assertEqual(result.returncode, 23)
        with runtime.installation_lock(self.target):
            pass

    def test_existing_unowned_directory_preserved(self):
        self.target.mkdir()
        sentinel = self.target / "owner-data"
        sentinel.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "E_EXISTING_STATE"):
            self.create()
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_uncheckpointed_file_is_preserved(self):
        installation = self.create()
        path = self.target / "orphan.key"
        path.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "E_INCOMPLETE"):
            installation.write("orphan.key", b"replace")
        self.assertEqual(path.read_bytes(), b"preserve")

    def test_interruption_after_secret_write_recovers_exact_recorded_value(self):
        installation = self.create()
        save = installation.save
        calls = 0

        def checkpoint():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic crash after durable key write")
            save()

        with (
            patch.object(installation, "save", side_effect=checkpoint),
            self.assertRaises(OSError),
        ):
            installation.write("recovered.key", b"original durable credential")
        resumed = self.create()
        resumed.write("recovered.key", b"must not rotate this value")
        self.assertEqual(
            (self.target / "recovered.key").read_bytes(), b"original durable credential"
        )
        self.assertNotIn("pendingWrite", resumed.state)

    def test_pending_write_tampering_is_not_adopted(self):
        installation = self.create()
        installation.state["pendingWrite"] = {
            "path": "key",
            "sha256": "a" * 64,
            "uid": None,
        }
        installation.save()
        (self.target / "key").write_bytes(b"unrelated")
        with self.assertRaisesRegex(ValueError, "E_CHANGED"):
            installation.write("key", b"regenerate")

    def test_changed_file_refuses_further_writes(self):
        installation = self.create()
        installation.write("secret.key", b"first")
        (self.target / "secret.key").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "E_CHANGED"):
            installation.write("secret.key", b"regenerate")

    def test_health_is_not_completed_owner_setup(self):
        installation = self.create()
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = (
            b"<html>fixture login</html>"
        )
        with (
            patch.object(installation, "compose", return_value='{"status":"UP"}'),
            patch("runtime.ssl.create_default_context"),
            patch("runtime.urllib.request.build_opener") as opener,
        ):
            opener.return_value.open.return_value = response
            installation.check_health()
        self.assertEqual(installation.state["stage"], "services-healthy")
        self.assertEqual(installation.state["ownerSetup"], "not-verified")
        self.assertEqual(installation.state["backup"], "not-configured")

    def test_unhealthy_core_does_not_complete(self):
        installation = self.create()
        with (
            patch.object(installation, "compose", return_value='{"status":"DOWN"}'),
            self.assertRaisesRegex(ValueError, "E_CORE"),
        ):
            installation.check_health()
        self.assertNotEqual(installation.state["stage"], "services-healthy")

    def test_child_output_is_not_exposed(self):
        with patch(
            "runtime.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "TOKEN", "PASSWORD"),
        ):
            with self.assertRaises(ValueError) as error:
                runtime.execute(["docker", "compose"])
            self.assertNotIn("TOKEN", str(error.exception))
            self.assertNotIn("PASSWORD", str(error.exception))


class ContractTests(unittest.TestCase):
    def test_locale_parity(self):
        root = Path(__file__).resolve().parents[1]
        en = json.loads((root / "locales/en.json").read_text(encoding="utf-8"))
        de = json.loads((root / "locales/de.json").read_text(encoding="utf-8"))
        self.assertEqual(set(en), set(de))
        self.assertTrue(
            all(
                isinstance(value, str) and value
                for value in [*en.values(), *de.values()]
            )
        )


if __name__ == "__main__":
    unittest.main()
