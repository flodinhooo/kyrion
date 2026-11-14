"""Real loopback HTTP/journals; registry and Ollama payloads are synthetic."""

import hashlib
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ollama_models as models
import ollama_runtime
from models import load_catalog
from recovery import load_installation
from runtime import Installation


class ModelOperations(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name) / "installation"
        self.installation = Installation(
            self.target,
            {"release": "1.0.0", "architecture": "linux/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.enterContext(patch("operational_restore.require_admin"))
        self.enterContext(patch("update_worker.validate_host"))
        self.catalog = load_catalog()
        self.manifest = json.dumps(
            {
                "schemaVersion": 2,
                "config": {"size": 10, "digest": "sha256:" + "a" * 64},
                "layers": [{"size": 20, "digest": "sha256:" + "b" * 64}],
            }
        ).encode()
        self.model = self.catalog["models"][0]
        self.model.update(
            manifestSha256=hashlib.sha256(self.manifest).hexdigest(), downloadBytes=30
        )
        self.enterContext(
            patch.object(models, "cached_catalog", return_value=self.catalog)
        )
        self.fetch = self.enterContext(
            patch.object(models, "fetch_document", return_value=self.manifest)
        )
        self.available = [
            {"name": "foreign:preserved", "size": 100, "digest": "d" * 64}
        ]
        self.running = []
        self.mode = "normal"
        self.mutations = []
        self.progress = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                values = {
                    "/api/version": {"version": "0.99.1"},
                    "/api/tags": {"models": fixture.available},
                    "/api/ps": {"models": fixture.running},
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(values[self.path]).encode())

            def request_model(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fixture.mutations.append((self.command, self.path, body))
                return body["model"]

            def do_POST(self):
                name = self.request_model()
                if fixture.mode == "drip":
                    for part in b"HTTP/1.1 200 OK\r\nX-Slow: " + b"a" * 60:
                        try:
                            self.wfile.write(bytes([part]))
                            self.wfile.flush()
                        except OSError:
                            break
                        threading.Event().wait(0.03)
                    return
                self.send_response(302 if fixture.mode == "redirect" else 200)
                self.send_header("Content-Type", "application/x-ndjson")
                if fixture.mode == "redirect":
                    self.send_header("Location", "https://never-contact.invalid")
                self.end_headers()
                if fixture.mode == "redirect":
                    return
                if fixture.mode == "error":
                    self.wfile.write(
                        b'{"error":"private-fixture-detail-do-not-display"}\n'
                    )
                    return
                if fixture.mode == "duplicate":
                    self.wfile.write(b'{"status":"success","status":"other"}\n')
                    return
                if fixture.mode == "oversize":
                    self.wfile.write(b"x" * (models.LINE_LIMIT + 1))
                    return
                record = {
                    "status": "pulling sha256:" + "b" * 64,
                    "digest": "sha256:" + "b" * 64,
                    "total": 20,
                    "completed": 10,
                }
                self.wfile.write(json.dumps(record).encode() + b"\n")
                if fixture.mode == "cut":
                    return
                digest = (
                    fixture.model["manifestSha256"]
                    if fixture.mode != "mismatch"
                    else "e" * 64
                )
                if fixture.mode != "success-without-model":
                    fixture.available.append(
                        {"name": name, "size": 30, "digest": digest}
                    )
                if fixture.mode == "unrelated":
                    fixture.available.append(
                        {"name": "unrelated:new", "size": 1, "digest": "f" * 64}
                    )
                if fixture.mode != "completed-cut":
                    self.wfile.write(
                        b'{"status":"verifying sha256 digest"}\n{"status":"success"}\n'
                    )

            def do_DELETE(self):
                name = self.request_model()
                fixture.available[:] = [
                    row for row in fixture.available if row["name"] != name
                ]
                if fixture.mode == "remove-cut":
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                self.send_response(200)
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port
        ollama_runtime.select(self.target, self.port, review=lambda _summary: True)

    def pull(self, review=lambda _summary: True):
        return models.pull(
            self.target, self.model["id"], review=review, progress=self.progress.append
        )

    def test_pull_requires_review_and_confirms_expected_inventory(self):
        review = Mock(return_value=True)
        result = self.pull(review)
        self.assertTrue(result["runtimeReportedAvailable"])
        self.assertFalse(result["independentBlobVerification"])
        self.assertFalse(result["aiServiceConnected"])
        self.assertEqual(review.call_args.args[0]["model"]["license"], "Apache-2.0")
        self.assertEqual(review.call_args.args[0]["model"]["downloadBytes"], 30)
        self.assertIsNone(review.call_args.args[0]["modelStoreCapacityBytes"])
        self.assertEqual(
            self.mutations,
            [
                (
                    "POST",
                    "/api/pull",
                    {"model": self.model["id"], "stream": True, "insecure": False},
                )
            ],
        )
        self.assertEqual(
            self.progress[0],
            {"phase": "downloading", "totalBytes": 20, "completedBytes": 10},
        )
        self.assertTrue(ollama_runtime.status(self.target)["selectionMatchesCurrent"])
        self.assertEqual(
            load_installation(self.target).state["ollamaModelOperation"]["phase"],
            "complete",
        )

    def test_inactive_or_unselected_installation_cannot_mutate_models(self):
        installation = load_installation(self.target)
        installation.state["authority"] = {"status": "retired"}
        installation.save()
        with self.assertRaisesRegex(ValueError, "E_AUTHORITY_INACTIVE"):
            self.pull()
        installation.state.pop("authority")
        installation.state.pop("ollamaRuntime")
        installation.save()
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_SELECTION"):
            self.pull()
        self.assertFalse(self.mutations)

    def test_port_cannot_override_the_selected_runtime(self):
        wrong = self.port + 1 if self.port < 65535 else self.port - 1
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_ENDPOINT"):
            models.pull(
                self.target, self.model["id"], port=wrong, review=lambda _summary: True
            )
        self.assertFalse(self.mutations)

    def test_malformed_operation_journal_fails_before_runtime_access(self):
        installation = load_installation(self.target)
        installation.state["ollamaModelOperation"] = {"unexpected": "never-display"}
        installation.save()
        with (
            patch.object(models, "probe") as probe,
            self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_JOURNAL"),
        ):
            self.pull()
        probe.assert_not_called()
        self.assertFalse(self.mutations)

    def test_success_stream_without_installed_model_is_not_completion(self):
        self.mode = "success-without-model"
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_RESULT"):
            self.pull()
        self.assertEqual(
            load_installation(self.target).state["ollamaModelOperation"]["phase"],
            "interrupted",
        )

    def test_cancelled_removal_preserves_the_model(self):
        self.pull()
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_CANCELLED"):
            models.remove(self.target, self.model["id"], review=lambda _summary: False)
        self.assertEqual(len(self.mutations), 1)
        self.assertIn(self.model["id"], [row["name"] for row in self.available])

    def test_cancel_does_not_download_or_write_operation(self):
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_CANCELLED"):
            self.pull(lambda _summary: False)
        self.assertFalse(self.mutations)
        self.assertNotIn("ollamaModelOperation", load_installation(self.target).state)

    def test_wrong_registry_hash_fails_before_review_or_download(self):
        self.fetch.return_value = b"unexpected manifest"
        review = Mock(return_value=True)
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_SOURCE"):
            self.pull(review)
        review.assert_not_called()
        self.assertFalse(self.mutations)

    def test_existing_conflicting_tag_is_never_overwritten(self):
        self.available.append(
            {"name": self.model["id"], "size": 30, "digest": "e" * 64}
        )
        ollama_runtime.select(self.target, self.port, review=lambda _summary: True)
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_CONFLICT"):
            self.pull()
        self.fetch.assert_not_called()
        self.assertFalse(self.mutations)

    def test_interrupted_pull_survives_reload_and_explicit_repeat(self):
        self.mode = "cut"
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_INTERRUPTED"):
            self.pull()
        self.assertEqual(
            load_installation(self.target).state["ollamaModelOperation"]["phase"],
            "interrupted",
        )
        self.mode = "normal"
        self.pull()
        self.assertEqual(len(self.mutations), 2)

    def test_lost_completion_reconciles_without_second_download(self):
        self.mode = "completed-cut"
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_INTERRUPTED"):
            self.pull()
        self.mode = "normal"
        self.pull()
        self.assertEqual(len(self.mutations), 1)
        self.assertTrue(ollama_runtime.status(self.target)["selectionMatchesCurrent"])

    def test_unexpected_digest_is_not_success_and_is_not_automatically_deleted(self):
        self.mode = "mismatch"
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_RESULT"):
            self.pull()
        self.assertEqual(
            load_installation(self.target).state["ollamaModelOperation"]["phase"],
            "interrupted",
        )
        self.assertEqual(len(self.mutations), 1)
        self.assertIn("e" * 64, [row["digest"] for row in self.available])

    def test_unrelated_inventory_change_is_not_silently_adopted(self):
        self.mode = "unrelated"
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_CHANGED"):
            self.pull()
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_CHANGED"):
            self.pull()
        self.assertEqual(len(self.mutations), 1)

    def test_provider_error_duplicate_oversize_and_redirect_are_not_success(self):
        for mode in ("error", "duplicate", "oversize", "redirect"):
            self.mode = mode
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_PROTOCOL"),
            ):
                self.pull()
            job = load_installation(self.target).state["ollamaModelOperation"]
            self.assertEqual(job["phase"], "interrupted")
            self.assertNotIn("private-fixture-detail", json.dumps(job))

    def test_absolute_deadline_also_bounds_dripping_headers(self):
        self.mode = "drip"
        started = time.monotonic()
        with (
            patch.object(models, "OPERATION_SECONDS", 0.1),
            self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_INTERRUPTED"),
        ):
            self.pull()
        self.assertLess(time.monotonic() - started, 1.0)

    def test_remove_is_separate_and_preserves_other_models(self):
        self.pull()
        review = Mock(return_value=True)
        result = models.remove(self.target, self.model["id"], review=review)
        self.assertFalse(result["runtimeReportedAvailable"])
        self.assertTrue(review.call_args.args[0]["otherApplicationsMayUseModel"])
        self.assertEqual([row["name"] for row in self.available], ["foreign:preserved"])
        self.assertEqual(
            self.mutations[-1], ("DELETE", "/api/delete", {"model": self.model["id"]})
        )

    def test_loaded_alias_is_refused_and_load_after_review_is_rechecked(self):
        self.pull()
        row = {
            "name": "alias:loaded",
            "size": 30,
            "digest": self.model["manifestSha256"],
            "size_vram": 10,
        }
        self.running[:] = [row]
        review = Mock(return_value=True)
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_IN_USE"):
            models.remove(self.target, self.model["id"], review=review)
        review.assert_not_called()
        self.running.clear()

        def load_during_review(_summary):
            self.running.append(row)
            return True

        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_IN_USE"):
            models.remove(self.target, self.model["id"], review=load_during_review)
        self.assertEqual(len(self.mutations), 1)

    def test_lost_removal_acknowledgement_reconciles_without_second_delete(self):
        self.pull()
        self.mode = "remove-cut"
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_INTERRUPTED"):
            models.remove(self.target, self.model["id"], review=lambda _summary: True)
        self.mode = "normal"
        models.remove(self.target, self.model["id"], review=lambda _summary: True)
        self.assertEqual([row[0] for row in self.mutations], ["POST", "DELETE"])

    def test_malformed_progress_and_private_status_are_not_rendered(self):
        for value in (
            {"status": "pulling", "total": True},
            {"status": "pulling", "total": 1, "completed": 2},
            {"status": "pulling", "digest": "invalid"},
            {"status": "success", "error": "secret"},
        ):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "E_OLLAMA_MODEL_PROTOCOL"),
            ):
                models.progress_record(value)
        self.assertEqual(
            models.progress_record({"status": "private raw provider detail"}),
            {"phase": "running"},
        )
