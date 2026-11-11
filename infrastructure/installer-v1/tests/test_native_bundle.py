"""Synthetic signed ZIP/PE fixtures. No runtime executable is executed here."""

import base64
import copy
import hashlib
import json
import runpy
import shutil
import stat
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_bundle
import test_release_policy as signature_fixture


def synthetic_pe():
    raw = bytearray(256)
    raw[:2] = b"MZ"
    struct.pack_into("<I", raw, 60, 128)
    raw[128:134] = b"PE\0\0\x64\x86"
    return bytes(raw)


class NativeBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.files = {
            name: synthetic_pe()
            if name.endswith(".exe")
            else b"Synthetic public fixture"
            for name in native_bundle.REQUIRED_FILES
        }

    def bundle(self, contents=None, symlink=None):
        contents = self.files if contents is None else contents
        archive = self.root / "kyrion-windows-amd64.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as stream:
            for name, value in sorted(contents.items()):
                if name == symlink:
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    stream.writestr(info, value)
                else:
                    stream.writestr(name, value)
        versions = {
            "core": "1.2.3",
            "web": "1.2.3",
            "java": "21.0.9+10",
            "node": "22.21.1",
            "postgres": "17.6",
            "caddy": "2.10.2",
        }
        manifest = {
            "schemaVersion": 2,
            "runtime": "windows-native",
            "release": "1.2.3",
            "architecture": "windows/amd64",
            "compatibility": {"api": 1, "schema": 48, "postgresMajor": 17},
            "components": {
                name: {
                    "version": version,
                    "sourceUrl": "https://synthetic.example.test/source",
                    "license": "fixture-only",
                    "licenseUrl": "https://synthetic.example.test/license",
                }
                for name, version in versions.items()
            },
            "artifact": {
                "name": archive.name,
                "bytes": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            },
            "files": [
                {
                    "path": name,
                    "bytes": len(value),
                    "sha256": hashlib.sha256(value).hexdigest(),
                }
                for name, value in sorted(contents.items())
            ],
        }
        self.write_manifest(manifest)
        return manifest

    def write_manifest(self, manifest):
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def signed_bundle(self):
        if not shutil.which("openssl"):
            self.skipTest("Actual detached signature verification requires OpenSSL")
        fixture = signature_fixture.SignatureTests(
            methodName="test_tampered_payload_is_rejected"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        manifest = self.bundle()
        signed = json.loads(fixture.sign(manifest))
        (self.root / "manifest.json").write_bytes(base64.b64decode(signed["payload"]))
        (self.root / "manifest.sig").write_bytes(base64.b64decode(signed["signature"]))
        return manifest, fixture.root / "public.pem"

    def test_signature_result_binds_interpreted_bytes_not_later_file_contents(self):
        manifest, public_key = self.signed_bundle()
        original = native_bundle.verify_signature

        def mutate_after_verification(*args):
            raw = original(*args)
            self.write_manifest({**manifest, "release": "9.9.9"})
            return raw

        with patch(
            "native_bundle.verify_signature", side_effect=mutate_after_verification
        ):
            self.assertEqual(
                native_bundle.authenticate(self.root, public_key), manifest
            )

    def test_actual_unpack_repeat_and_refusal_to_replace_changed_public_file(self):
        _, public_key = self.signed_bundle()
        destination = self.root / "payload"
        first = native_bundle.unpack(self.root, public_key, destination)
        with patch(
            "native_bundle.atomic_json", wraps=native_bundle.atomic_json
        ) as writes:
            repeated = native_bundle.unpack(self.root, public_key, destination)
        self.assertEqual(writes.call_count, 2 + len(self.files) // 128)
        self.assertEqual(first, repeated)
        self.assertTrue(first["payloadVerified"])
        self.assertFalse(first["runtimeActivated"])
        self.assertEqual(first["files"], len(self.files))
        target = destination / "app/web/server.js"
        target.write_bytes(b"preserve altered original")
        with self.assertRaisesRegex(ValueError, "E_NATIVE_CHANGED"):
            native_bundle.unpack(self.root, public_key, destination)
        self.assertEqual(target.read_bytes(), b"preserve altered original")

    def test_interruption_preserves_partial_and_resumes_verified_payload(self):
        _, public_key = self.signed_bundle()
        destination = self.root / "payload"

        def interrupted(_archive, _name, temporary, _expected):
            temporary.write_bytes(b"partial public runtime")
            raise OSError("synthetic developer interruption")

        with (
            patch("native_bundle.copy_member", side_effect=interrupted),
            self.assertRaises(OSError),
        ):
            native_bundle.unpack(self.root, public_key, destination)
        result = native_bundle.unpack(self.root, public_key, destination)
        self.assertEqual(result["preservedPartials"], 1)
        partials = list(destination.glob(".native-part-*"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].read_bytes(), b"partial public runtime")
        self.assertEqual(
            native_bundle.unpack(self.root, public_key, destination), result
        )

    def test_legacy_receipt_and_killed_journal_write_resume_without_adoption(self):
        _, public_key = self.signed_bundle()
        destination = self.root / "payload"
        native_bundle.unpack(self.root, public_key, destination)
        receipt = destination / ".kyrion-native-payload.json"
        state = json.loads(receipt.read_text())
        state["formatVersion"] = 1
        state["completed"] = sorted(self.files)
        receipt.write_text(json.dumps(state))
        orphan = destination / "..kyrion-native-payload.json.0123456789abcdef"
        orphan.write_bytes(b"interrupted metadata, never adopted")
        result = native_bundle.unpack(self.root, public_key, destination)
        migrated = json.loads(receipt.read_text())
        self.assertTrue(result["payloadVerified"])
        self.assertEqual(migrated["formatVersion"], 2)
        self.assertEqual(migrated["completed"], len(self.files))
        self.assertEqual(orphan.read_bytes(), b"interrupted metadata, never adopted")
        self.assertLess(receipt.stat().st_size, 1024)

    def test_unpack_acquires_exclusive_installation_lock(self):
        from runtime import installation_lock

        _, public_key = self.signed_bundle()
        destination = self.root / "payload"
        with (
            installation_lock(destination),
            self.assertRaisesRegex(ValueError, "E_LOCKED"),
        ):
            native_bundle.unpack(self.root, public_key, destination)
        self.assertFalse(destination.exists())

    def test_unowned_directory_and_unexpected_entries_are_preserved(self):
        _, public_key = self.signed_bundle()
        destination = self.root / "payload"
        destination.mkdir()
        sentinel = destination / "operator-data.txt"
        sentinel.write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "E_NATIVE_EXISTING"):
            native_bundle.unpack(self.root, public_key, destination)
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_complete_synthetic_payload_is_validated_without_execution(self):
        expected = self.bundle()
        self.assertEqual(native_bundle.validate(self.root), expected)

    def test_build_tool_produces_a_valid_unsigned_profile_and_preserves_outputs(self):
        manifest = self.bundle()
        profile = self.root / "profile"
        for name, value in self.files.items():
            path = profile / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        builder = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "release/build-windows-bundle.py")
        )["build"]
        metadata = {
            key: manifest[key] for key in ("release", "components", "compatibility")
        }
        output = self.root / "built"
        result = builder(profile, metadata, output)
        self.assertFalse(result["signed"])
        self.assertFalse(result["platformInstallationAccepted"])
        self.assertEqual(native_bundle.validate(output)["files"], manifest["files"])
        original = (output / "manifest.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "E_NATIVE_BUILD_INPUT"):
            builder(profile, metadata, output)
        self.assertEqual((output / "manifest.json").read_bytes(), original)
        (profile / "app/web/.env.local").write_text(
            "private-synthetic-fixture", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            builder(profile, metadata, self.root / "blocked")
        self.assertFalse((self.root / "blocked").exists())

    def test_windows_alias_private_reserved_and_traversal_paths_fail(self):
        for path in (
            "app/web/.env.local",
            "app/web/.ssh/id_rsa",
            "app/web/../../outside",
            "app/web/aux.txt",
            "app/web/file:stream",
            "app/web/file.",
            "app/web/a\\b",
            "app/web/NODE.exe",
            "/app/web/file",
        ):
            with self.subTest(path=path):
                if path == "app/web/NODE.exe":
                    contents = {
                        **self.files,
                        "app/web/node.exe": synthetic_pe(),
                        path: synthetic_pe(),
                    }
                else:
                    contents = {**self.files, path: b"fixture"}
                self.bundle(contents)
                with self.assertRaises(ValueError):
                    native_bundle.validate(self.root)

    def test_link_non_windows_binary_and_missing_license_fail(self):
        node = "runtime/node/node.exe"
        self.bundle(symlink=node)
        with self.assertRaisesRegex(ValueError, "E_NATIVE_ARCHIVE_ENTRY"):
            native_bundle.validate(self.root)
        self.bundle({**self.files, node: b"\x7fELFwrong-platform"})
        with self.assertRaisesRegex(ValueError, "E_NATIVE_BINARY_ARCHITECTURE"):
            native_bundle.validate(self.root)
        self.bundle(
            {
                name: value
                for name, value in self.files.items()
                if name != "licenses/java.txt"
            }
        )
        with self.assertRaisesRegex(ValueError, "E_NATIVE_REQUIRED_FILES"):
            native_bundle.validate(self.root)

    def test_hashes_and_component_schema_requirements_are_checked(self):
        manifest = self.bundle()
        (self.root / manifest["artifact"]["name"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "E_NATIVE_DIGEST"):
            native_bundle.validate(self.root)
        manifest = self.bundle()
        for section, key, value in (
            ("compatibility", "postgresMajor", 18),
            ("compatibility", "api", True),
            (
                "components",
                "java",
                {**manifest["components"]["java"], "version": "25.0.1"},
            ),
        ):
            broken = copy.deepcopy(manifest)
            broken[section][key] = value
            self.write_manifest(broken)
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                native_bundle.validate(self.root)

    @unittest.skipUnless(
        shutil.which("openssl"), "Actual detached Ed25519 verification requires OpenSSL"
    )
    def test_detached_signature_is_verified_before_archive_interpretation(self):
        fixture = signature_fixture.SignatureTests(
            methodName="test_tampered_payload_is_rejected"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        manifest = self.bundle()
        signed = json.loads(fixture.sign(manifest))
        (self.root / "manifest.json").write_bytes(base64.b64decode(signed["payload"]))
        (self.root / "manifest.sig").write_bytes(base64.b64decode(signed["signature"]))
        public_key = fixture.root / "public.pem"
        self.assertEqual(native_bundle.authenticate(self.root, public_key), manifest)
        (self.root / "manifest.sig").write_bytes(b"x" * 64)
        with (
            patch("native_bundle.validate") as validator,
            self.assertRaisesRegex(ValueError, "E_SIGNATURE"),
        ):
            native_bundle.authenticate(self.root, public_key)
        validator.assert_not_called()
