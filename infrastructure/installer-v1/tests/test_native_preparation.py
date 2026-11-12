"""Native preparation on real temporary files; OS registration is never called."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_runtime
from runtime import Installation


@unittest.skipUnless(
    importlib.util.find_spec("cryptography"), "Installer runtime dependency required"
)
class Preparation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "installation"
        self.installation = Installation(
            self.root,
            {"release": "1.2.3", "architecture": "windows/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.installation.state["backend"] = "windows-native"
        self.installation.save()

    def configure(self):
        native_runtime.configure(self.installation, {}, "a" * 64)

    def test_configuration_repeats_without_rotating_keys_or_touching_external_runtime(
        self,
    ):
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        foreign = self.root.parent / "foreign-ollama.conf"
        foreign.write_bytes(b"preserve operator settings")
        self.configure()
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in (self.root / "secrets").iterdir()
        }
        key = (self.root / "data/tls/key.pem").read_bytes()
        cert = (self.root / "data/tls/cert.pem").read_bytes()
        self.configure()
        self.assertEqual(
            before,
            {
                path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in (self.root / "secrets").iterdir()
            },
        )
        self.assertEqual((self.root / "data/tls/key.pem").read_bytes(), key)
        self.assertEqual((self.root / "data/tls/cert.pem").read_bytes(), cert)
        self.assertEqual(
            x509.load_pem_x509_certificate(cert).public_key().public_numbers(),
            load_pem_private_key(key, password=None).public_key().public_numbers(),
        )
        self.assertEqual(foreign.read_bytes(), b"preserve operator settings")
        self.assertEqual(len((self.root / "secrets/credential.key").read_bytes()), 32)
        self.assertNotIn(
            (self.root / "secrets/postgres-password").read_text().strip(),
            json.dumps(self.installation.state),
        )
        sql = (self.root / "native-create-db.sql").read_text()
        self.assertIn("\n\\gexec\n", sql)

    def test_interruption_after_private_key_publication_keeps_matching_certificate(
        self,
    ):
        real_write = self.installation.write

        def interrupted(relative, value, *args, **kwargs):
            real_write(relative, value, *args, **kwargs)
            if relative == "data/tls/key.pem":
                raise OSError("synthetic process interruption")

        with (
            patch.object(self.installation, "write", side_effect=interrupted),
            self.assertRaises(OSError),
        ):
            self.configure()
        key = (self.root / "data/tls/key.pem").read_bytes()
        self.configure()
        self.assertEqual((self.root / "data/tls/key.pem").read_bytes(), key)
        self.assertTrue((self.root / "data/tls/cert.pem").is_file())

    def test_private_directory_is_published_with_its_initial_journal(self):
        target = self.root.parent / "atomic-installation"
        calls = []

        def create(path, action):
            self.assertEqual(action, "create")
            calls.append(path)
            path.mkdir(mode=0o700)

        with patch("native_runtime.permissions", side_effect=create):
            installation = Installation(
                target,
                {"release": "1.2.3", "architecture": "windows/amd64"},
                "a" * 64,
                "fixture.test",
                "127.0.0.1",
                directory_factory=native_runtime.create_journalled_root,
            )
        saved = json.loads((target / "install-state.json").read_text())
        self.assertEqual(saved["installationId"], installation.state["installationId"])
        self.assertEqual(saved["rootPath"], str(target.resolve()))
        self.assertFalse(calls[0].exists())
        self.assertNotEqual(calls[0], target)

    def test_interruption_before_publication_preserves_private_staging_only(self):
        from runtime import atomic_json

        target = self.root.parent / "interrupted-installation"

        def create(path, _action):
            path.mkdir(mode=0o700)

        def interrupted(path, value):
            atomic_json(path, value)
            raise OSError("synthetic publication interruption")

        with (
            patch("native_runtime.permissions", side_effect=create),
            patch("native_runtime.atomic_json", side_effect=interrupted),
            self.assertRaises(OSError),
        ):
            Installation(
                target,
                {"release": "1.2.3", "architecture": "windows/amd64"},
                "a" * 64,
                "fixture.test",
                "127.0.0.1",
                directory_factory=native_runtime.create_journalled_root,
            )
        self.assertFalse(target.exists())
        stages = list(target.parent.glob(target.name + ".creating-*"))
        self.assertEqual(len(stages), 1)
        saved = json.loads((stages[0] / "install-state.json").read_text())
        self.assertEqual(saved["files"], {})
        self.assertEqual(saved["rootPath"], str(target.resolve()))

    def test_unrecognized_database_is_never_reinitialized(self):
        self.configure()
        sentinel = self.root / "data/postgres/operator-data"
        sentinel.write_bytes(b"preserve")
        with (
            patch("native_runtime.pg_run") as runner,
            self.assertRaisesRegex(ValueError, "E_NATIVE_EXISTING_DATABASE"),
        ):
            native_runtime.initialize_database(self.installation)
        runner.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_interrupted_init_is_preserved_and_completed_directory_adopted_only_from_intent(
        self,
    ):
        self.configure()

        def failed(_installation, directory, resume_only=False):
            (directory / "partial").write_bytes(b"preserve interrupted bytes")
            raise OSError("synthetic init interruption")

        with (
            patch("native_runtime.bootstrap_database", side_effect=failed),
            self.assertRaises(OSError),
        ):
            native_runtime.initialize_database(self.installation)

        def success(_installation, directory, resume_only=False):
            if resume_only:
                return False
            (directory / "PG_VERSION").write_text("17\n")
            (directory / "global").mkdir()
            (directory / "global/pg_control").write_bytes(b"synthetic control")
            (directory / "postgresql.conf").write_text("# synthetic initdb output\n")
            return True

        with patch("native_runtime.bootstrap_database", side_effect=success):
            native_runtime.initialize_database(self.installation)
        preserved = list((self.root / "data").glob("preserved-init-*"))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(
            (preserved[0] / "partial").read_bytes(), b"preserve interrupted bytes"
        )
        self.assertEqual(self.installation.state["nativeDatabase"], "initialized")
        with patch("native_runtime.bootstrap_database") as runner:
            native_runtime.initialize_database(self.installation)
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
