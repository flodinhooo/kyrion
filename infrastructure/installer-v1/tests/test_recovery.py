"""Real archive/GnuPG tests and injected runtime capture/repair failure tests."""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance
import recovery
from runtime import Installation


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.write_bytes(b"synthetic data and private keys")

    def archive(self):
        path = self.root / "backup.tar"
        recovery.create_archive(
            {"database.dump": self.source}, {"postgresMajor": 17, "schema": 46}, path
        )
        return path

    def test_archive_integrity_roundtrip(self):
        manifest = recovery.inspect_archive(self.archive())
        self.assertEqual(
            manifest["files"]["database.dump"]["bytes"], self.source.stat().st_size
        )

    def test_rejects_unsafe_archive_members(self):
        for name in (
            "../keys",
            "/etc/passwd",
            "secrets/../../keys",
            "secrets/C:/keys",
            "secrets\\key",
            "./database.dump",
        ):
            with self.subTest(name=name):
                self.assertFalse(recovery.allowed_member(name))

    def test_tar_links_and_duplicates_are_not_extracted(self):
        for link in (True, False):
            path = self.root / ("link.tar" if link else "duplicate.tar")
            with tarfile.open(path, "w") as archive:
                item = tarfile.TarInfo("database.dump")
                if link:
                    item.type = tarfile.SYMTYPE
                    item.linkname = "/etc/passwd"
                    archive.addfile(item)
                else:
                    archive.addfile(item, io.BytesIO(b""))
                    archive.addfile(item, io.BytesIO(b""))
            with self.assertRaisesRegex(ValueError, "E_BACKUP_PATH"):
                recovery.inspect_archive(path)

    def test_modified_content_fails_digest(self):
        path = self.archive()
        damaged = self.root / "damaged.tar"
        damaged.write_bytes(
            path.read_bytes().replace(b"synthetic data", b"tampered! data", 1)
        )
        with self.assertRaisesRegex(ValueError, "E_BACKUP_INTEGRITY"):
            recovery.inspect_archive(damaged)

    @unittest.skipUnless(
        shutil.which("gpg"), "GnuPG required for actual encryption/decryption"
    )
    def test_actual_encrypted_backup_roundtrip_and_wrong_password(self):
        clear = self.archive()
        encrypted = self.root / "encrypted.gpg"
        password = "synthetic-recovery-password-123456"
        recovery.crypto(clear, encrypted, password)
        with recovery.verified_plaintext(encrypted, password) as (_, manifest, _):
            self.assertEqual(manifest["metadata"]["schema"], 46)
        with (
            self.assertRaisesRegex(ValueError, "E_BACKUP_INTEGRITY"),
            recovery.verified_plaintext(encrypted, "incorrect-synthetic-password-123"),
        ):
            self.fail("Unauthenticated plaintext must never be yielded")

    def test_short_recovery_password_refused_before_crypto(self):
        with self.assertRaisesRegex(ValueError, "E_RECOVERY_PASSWORD"):
            recovery.crypto(self.source, self.root / "encrypted", "short")

    def installation(self):
        installation = Installation(
            self.root / "installation",
            {"release": "1.2.3", "architecture": "linux/arm64"},
            "a" * 64,
            "kyrion.home.arpa",
            "192.168.1.2",
        )
        for name in (
            "secrets/credential.key",
            "secrets/audit-integrity.key",
            "secrets/postgres-password",
            "compose.yml",
            ".env",
        ):
            installation.write(name, b"fixture")
        return installation

    def test_capture_restarts_only_previously_running_core_after_dump_failure(self):
        installation = self.installation()
        commands = []

        def compose(*args):
            commands.append(args)
            if args[0] == "ps":
                return '{"Service":"core","State":"running"}'
            if args[0] == "exec":
                return "46"
            return ""

        with (
            patch.object(installation, "compose", side_effect=compose),
            patch(
                "recovery.subprocess.run",
                return_value=subprocess.CompletedProcess([], 1),
            ),
            self.assertRaisesRegex(ValueError, "E_BACKUP_DATABASE"),
        ):
            recovery.capture(
                installation, self.root / "output.gpg", "long-synthetic-password"
            )
        self.assertIn(("stop", "--timeout", "30", "core"), commands)
        self.assertEqual(commands[-1], ("start", "core"))
        self.assertFalse((self.root / "output.gpg").exists())

    def test_diagnostic_export_cannot_include_credentials_or_logs(self):
        installation = self.installation()
        installation.state["sessionToken"] = "private-session"
        installation.state["lastError"] = "credential=private-token"
        installation.state["configuration"]["password"] = "private-password"
        # Configuration is compared by the loader; extra unowned fields fail
        # closed rather than copying them. Inject the authority only for this
        # redaction fixture to verify the exporter itself is allowlisted.
        output = self.root / "report.json"
        with patch("maintenance.load_installation", return_value=installation):
            maintenance.diagnostic(installation.target, output)
        text = output.read_text()
        self.assertNotIn("private-", text)
        self.assertNotIn("sessionToken", text)
        self.assertIsNone(json.loads(text)["lastError"])

    def test_repair_restores_only_original_known_template(self):
        installation = self.installation()
        path = installation.target / "compose.yml"
        original = (
            (maintenance.ROOT / "templates/compose.yml")
            .read_text(encoding="utf-8")
            .encode("utf-8")
        )
        path.write_bytes(original)
        installation.state["files"]["compose.yml"] = recovery.sha256(path)
        installation.save()
        path.write_bytes(b"synthetically damaged config")
        with (
            patch(
                "maintenance.installation_lock", return_value=contextlib.nullcontext()
            ),
            patch("maintenance.runtime_checks"),
            patch.object(Installation, "start"),
        ):
            result = maintenance.repair(installation.target)
        self.assertEqual(result["repairedFiles"], ["compose.yml"])
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(list(path.parent.glob("compose.yml.repair-original-*")))

    def test_repair_never_regenerates_changed_secret(self):
        installation = self.installation()
        path = installation.target / "secrets/credential.key"
        path.write_bytes(b"changed original key")
        with (
            patch(
                "maintenance.installation_lock", return_value=contextlib.nullcontext()
            ),
            patch("maintenance.runtime_checks"),
            self.assertRaisesRegex(ValueError, "E_REPAIR_ORIGINAL_REQUIRED"),
        ):
            maintenance.repair(installation.target)
        self.assertEqual(path.read_bytes(), b"changed original key")

    def test_uninstall_data_choice_preserves_foreign_resources(self):
        installation = self.installation()
        sibling = self.root / "foreign-ollama-model"
        sibling.write_bytes(b"foreign model fixture")
        with (
            patch(
                "maintenance.installation_lock",
                side_effect=lambda target: contextlib.nullcontext(),
            ),
            patch("maintenance.runtime_checks"),
            patch.object(Installation, "compose", return_value="") as compose,
        ):
            result = maintenance.uninstall(installation.target, purge=False)
            self.assertFalse(result["dataRemoved"])
            self.assertTrue((installation.target / "secrets/credential.key").is_file())
            result = maintenance.uninstall(installation.target, purge=True)
            self.assertTrue(result["dataRemoved"])
            self.assertFalse(installation.target.exists())
            self.assertEqual(compose.call_count, 2)
            self.assertTrue(
                all(
                    call.args == ("down", "--timeout", "30")
                    for call in compose.call_args_list
                )
            )
        self.assertEqual(sibling.read_bytes(), b"foreign model fixture")


if __name__ == "__main__":
    unittest.main()
