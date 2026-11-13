"""Actual loopback HTTPS/range/hash tests; synthetic payloads never execute."""

import base64
import copy
import hashlib
import io
import json
import os
import ssl
import sys
import tarfile
import tempfile
import threading
import time
import unittest
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_native_bundle as native_fixture
import update_download
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from native_runtime import certificate, private_tls_key
from recovery import load_installation
from runtime import Installation


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.files = {"/runtime.bin": bytes(range(256)) * 8193}
        self.mode = "normal"
        self.requests = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                fixture.requests.append((self.path, self.headers.get("Range")))
                raw = fixture.files[self.path]
                ranged = self.headers.get("Range")
                offset = int(ranged[6:-1]) if ranged else 0
                mode = (
                    fixture.mode
                    if self.path != "/index.json" and self.path != "/manifest.json"
                    else "normal"
                )
                if mode == "redirect":
                    self.send_response(302)
                    self.send_header(
                        "Location", "https://never-contact.invalid.example.test/file"
                    )
                    self.end_headers()
                    return
                if mode == "ignore-range":
                    offset = 0
                self.send_response(206 if offset else 200)
                if offset:
                    self.send_header(
                        "Content-Range",
                        f"bytes {offset + (1 if mode == 'bad-range' else 0)}-{len(raw) - 1}/{len(raw)}",
                    )
                self.send_header(
                    "Content-Length",
                    str(len(raw) - offset + (1 if mode == "bad-length" else 0)),
                )
                if mode == "encoding":
                    self.send_header("Content-Encoding", "gzip")
                self.end_headers()
                if mode in {"bad-length", "bad-range", "encoding"}:
                    return
                if mode == "interrupt":
                    self.wfile.write(raw[offset : offset + max(1, len(raw) // 2)])
                    self.close_connection = True
                elif mode == "corrupt":
                    self.wfile.write(b"x" * (len(raw) - offset))
                else:
                    self.wfile.write(raw[offset:])

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        key = private_tls_key()
        key_path, cert_path = self.root / "test.key", self.root / "test.pem"
        key_path.write_bytes(key)
        cert_path.write_bytes(certificate("localhost", "127.0.0.1", key))
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(cert_path, key_path)
        server.socket = server_context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        self.url = "https://127.0.0.1:" + str(server.server_port)
        trusted_context = ssl.create_default_context(cafile=str(cert_path))
        original = urllib.request.build_opener
        self.original_opener = original
        self.enterContext(
            patch(
                "urllib.request.build_opener",
                side_effect=lambda *handlers: original(
                    *handlers, urllib.request.HTTPSHandler(context=trusted_context)
                ),
            )
        )
        self.item = {
            "name": "runtime.bin",
            "bytes": len(self.files["/runtime.bin"]),
            "sha256": hashlib.sha256(self.files["/runtime.bin"]).hexdigest(),
        }
        self.destination, self.partial = (
            self.root / "verified.bin",
            self.root / "download.partial",
        )

    def fetch(self):
        update_download.stream_artifact(
            self.url + "/runtime.bin", self.destination, self.partial, self.item
        )

    def test_interrupted_https_continues_with_real_range_and_final_hash(self):
        self.mode = "interrupt"
        with self.assertRaisesRegex(ValueError, "E_DOWNLOAD_INTERRUPTED"):
            self.fetch()
        self.assertFalse(self.destination.exists())
        offset = self.partial.stat().st_size
        self.assertGreater(offset, 0)
        self.mode = "normal"
        self.fetch()
        self.assertIn(("/runtime.bin", "bytes=" + str(offset) + "-"), self.requests)
        self.assertEqual(self.destination.read_bytes(), self.files["/runtime.bin"])
        count = len(self.requests)
        self.fetch()
        self.assertEqual(len(self.requests), count)

    def test_ignored_range_restarts_only_owned_partial(self):
        self.partial.write_bytes(self.files["/runtime.bin"][:321])
        self.mode = "ignore-range"
        self.fetch()
        self.assertEqual(self.destination.read_bytes(), self.files["/runtime.bin"])

    def test_wrong_range_is_rejected_without_mutating_prefix(self):
        self.partial.write_bytes(b"existing prefix")
        self.mode = "bad-range"
        with self.assertRaisesRegex(ValueError, "E_DOWNLOAD_RANGE"):
            self.fetch()
        self.assertEqual(self.partial.read_bytes(), b"existing prefix")
        self.assertFalse(self.destination.exists())

    def test_invalid_response_or_digest_never_publishes(self):
        for mode in ("bad-length", "encoding", "corrupt", "redirect"):
            self.mode = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.fetch()
            self.assertFalse(self.destination.exists())
        self.assertTrue(all(path == "/runtime.bin" for path, _ in self.requests))

    def staged_fixture(self):
        fixture = native_fixture.NativeBundleTests(
            methodName="test_actual_unpack_repeat_and_refusal_to_replace_changed_public_file"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        manifest = fixture.bundle()
        manifest["compatibility"]["schema"] = 49
        raw = json.dumps(manifest).encode()
        self.files["/manifest.json"] = raw
        self.files["/kyrion-windows-amd64.zip"] = (
            fixture.root / "kyrion-windows-amd64.zip"
        ).read_bytes()
        private = Ed25519PrivateKey.generate()
        now = int(time.time())
        trust = {
            "formatVersion": 1,
            "epoch": 1,
            "keys": [
                {
                    "id": "fixture",
                    "pem": private.public_key()
                    .public_bytes(
                        serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    .decode(),
                    "notBefore": now - 60,
                    "notAfter": now + 86400,
                    "usages": ["release-index", "trust-rotation"],
                }
            ],
        }
        candidate = {
            "version": "1.2.3",
            "platform": "windows/amd64",
            "minimumInstaller": "1.0.0",
            "fromSchemas": [49],
            "targetSchema": 49,
            "apiMin": 1,
            "apiMax": 1,
            "manifestUrl": self.url + "/manifest.json",
            "manifestSha256": hashlib.sha256(raw).hexdigest(),
            "notesUrl": self.url + "/notes",
            "schemaDowngradeSupported": False,
            "components": {
                name: component["version"]
                for name, component in manifest["components"].items()
            },
        }
        index = json.dumps(
            {
                "formatVersion": 1,
                "kind": "release-index",
                "sequence": 1,
                "expiresAt": now + 3600,
                "releases": [candidate],
            }
        ).encode()
        self.files["/index.json"] = json.dumps(
            {
                "keyId": "fixture",
                "payload": base64.b64encode(index).decode(),
                "signature": base64.b64encode(private.sign(index)).decode(),
            }
        ).encode()
        target = self.root / "installed"
        installation = Installation(
            target,
            {"release": "1.1.0", "architecture": "windows/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        installation.state["backend"] = "windows-native"
        installation.state["updatePolicy"] = {
            "formatVersion": 1,
            "revision": str(uuid.uuid4()),
            "enabled": False,
            "feed": self.url + "/index.json",
            "trust": trust,
            "workerFile": "maintenance-"
            + "a" * 32
            + (".exe" if os.name == "nt" else ""),
        }
        installation.save()
        self.enterContext(patch("operational_restore.require_admin"))
        self.enterContext(patch("update_worker.validate_host"))
        self.enterContext(
            patch(
                "update_worker.require_worker",
                side_effect=lambda inst, _policy: inst.verify_files(),
            )
        )
        self.enterContext(
            patch("build_identity.read_build", return_value={"version": "1.0.0"})
        )
        self.enterContext(patch("native_runtime.installed_schema", return_value="49"))
        self.enterContext(
            patch.object(
                Installation,
                "compose",
                side_effect=AssertionError(
                    "Downloads must never manipulate running services"
                ),
            )
        )
        return target, candidate

    def test_signed_candidate_download_and_revalidation_leave_runtime_unchanged(self):
        target, candidate = self.staged_fixture()
        result = update_download.download(
            target, review=lambda summary: summary["totalBytes"] > 0
        )
        self.assertTrue(result["payloadVerified"])
        self.assertFalse(result["installed"])
        self.assertFalse(result["runtimeActivated"])
        installation = load_installation(target)
        self.assertEqual(installation.configuration["release"], "1.1.0")
        reviewed = update_download.revalidate(installation, "1.0.0", 49)
        self.assertEqual(reviewed.manifest_sha256, candidate["manifestSha256"])
        with (
            patch("release_policy.time.time", return_value=time.time() + 7200),
            self.assertRaisesRegex(ValueError, "EXPIRED"),
        ):
            update_download.revalidate(installation, "1.0.0", 49)
        installation.state["updatePolicy"]["revision"] = str(uuid.uuid4())
        with self.assertRaisesRegex(ValueError, "E_UPDATE_POLICY_CHANGED"):
            update_download.revalidate(installation, "1.0.0", 49)

    def test_review_rejection_never_fetches_large_artifact(self):
        target, _ = self.staged_fixture()
        with self.assertRaisesRegex(ValueError, "E_CONFIRMATION"):
            update_download.download(target, review=lambda _: False)
        self.assertNotIn(
            "/kyrion-windows-amd64.zip", [path for path, _ in self.requests]
        )
        self.assertNotIn("updateDownload", load_installation(target).state)

    def test_manifest_hash_and_compatibility_checked_before_artifact_plan(self):
        _target, candidate = self.staged_fixture()
        changed = copy.deepcopy(candidate)
        changed["targetSchema"] = 50
        with self.assertRaisesRegex(ValueError, "E_UPDATE_COMPATIBILITY"):
            update_download.artifact_plan(self.files["/manifest.json"], changed)
        with self.assertRaisesRegex(ValueError, "E_DOWNLOAD_MANIFEST_DIGEST"):
            update_download.artifact_plan(
                self.files["/manifest.json"] + b" ", candidate
            )

    def test_production_transport_rejects_untrusted_certificate(self):
        with (
            patch("urllib.request.build_opener", self.original_opener),
            self.assertRaises(OSError),
        ):
            self.fetch()
        self.assertFalse(self.destination.exists())

    def test_whole_staging_resumes_after_actual_interrupted_https(self):
        target, _ = self.staged_fixture()
        self.mode = "interrupt"
        with self.assertRaisesRegex(ValueError, "E_DOWNLOAD_INTERRUPTED"):
            update_download.download(target, review=lambda _: True)
        interrupted = load_installation(target)
        self.assertEqual(interrupted.state["updateDownload"]["phase"], "downloading")
        self.assertEqual(
            interrupted.state["updateDownload"]["lastError"], "E_DOWNLOAD_INTERRUPTED"
        )
        files = copy.deepcopy(interrupted.state["files"])
        self.mode = "normal"
        result = update_download.download(target, review=lambda _: True)
        self.assertTrue(result["payloadVerified"])
        self.assertEqual(load_installation(target).state["files"], files)
        self.assertTrue(
            any(
                path.endswith(".zip") and ranged is not None
                for path, ranged in self.requests
            )
        )

    def test_linux_plan_and_actual_tar_image_identity_are_verified(self):
        from runtime import image_plan

        root = self.root / "linux-images"
        root.mkdir()
        release = "1.2.3"
        names = [
            "kyrion-core-amd64.tar",
            "kyrion-web-amd64.tar",
            "postgres-amd64.tar",
            "caddy-amd64.tar",
        ]
        manifest = {
            "schemaVersion": 1,
            "release": release,
            "architecture": "linux/amd64",
            "artifacts": [{"name": name} for name in names],
        }
        for name, tag in image_plan(manifest).items():
            with tarfile.open(root / name, "w") as archive:
                for member_name, data in (
                    (
                        "manifest.json",
                        json.dumps(
                            [{"RepoTags": [tag], "Config": "config.json"}]
                        ).encode(),
                    ),
                    ("config.json", b'{"architecture":"amd64","os":"linux"}'),
                ):
                    member = tarfile.TarInfo(member_name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
        manifest["artifacts"] = [
            {
                "name": name,
                "bytes": (root / name).stat().st_size,
                "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
            }
            for name in names
        ]
        raw = json.dumps(manifest).encode()
        (root / "manifest.json").write_bytes(raw)
        candidate = {
            "version": release,
            "platform": "linux/amd64",
            "manifestSha256": hashlib.sha256(raw).hexdigest(),
            "manifestUrl": self.url + "/manifest.json",
            "components": {
                "core": release,
                "web": release,
                "postgres": "17.6-alpine",
                "caddy": "2.10.2-alpine",
            },
        }
        self.assertEqual(len(update_download.artifact_plan(raw, candidate)), 4)
        self.assertEqual(
            update_download.validate_payload(root, raw, candidate).manifest, manifest
        )
        candidate["components"]["postgres"] = "18.0-alpine"
        with self.assertRaisesRegex(ValueError, "E_UPDATE_COMPATIBILITY"):
            update_download.artifact_plan(raw, candidate)
