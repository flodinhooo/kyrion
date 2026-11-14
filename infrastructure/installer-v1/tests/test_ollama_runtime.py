"""Real loopback TCP/HTTP and journals; server payloads are synthetic Ollama."""

import copy
import json
import os
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
import local_listeners
import ollama_runtime as runtime
from recovery import load_installation
from runtime import Installation


class OllamaRuntime(unittest.TestCase):
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
        self.requests = []
        self.model = {"name": "fixture:small", "size": 2048, "digest": "a" * 64}
        self.values = {
            "/api/version": {"version": "0.99.1"},
            "/api/tags": {"models": [self.model]},
            "/api/ps": {"models": [{**self.model, "size_vram": 1024}]},
        }
        self.mode = "normal"
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                fixture.requests.append(("GET", self.path))
                if fixture.mode == "hang":
                    threading.Event().wait(2)
                    return
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
                self.send_header("Content-Type", "application/json")
                if fixture.mode == "redirect":
                    self.send_header(
                        "Location", "https://never-contact.invalid.example.test"
                    )
                self.end_headers()
                if fixture.mode == "duplicate":
                    raw = b'{"version":"0.99.1","version":"0.99.2"}'
                elif fixture.mode == "oversize":
                    raw = b"x" * (runtime.LIMIT + 1)
                else:
                    raw = json.dumps(fixture.values[self.path]).encode()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port

    def test_real_os_listener_probe_and_normalized_models(self):
        self.assertEqual(local_listeners.loopback_bindings(self.port), ("127.0.0.1",))
        observed = runtime.probe(self.port)
        self.assertTrue(observed["connectionTested"])
        self.assertEqual(observed["models"][0]["digest"], "a" * 64)
        self.assertEqual(observed["runningModels"][0]["vramBytesObserved"], 1024)
        self.assertIsNone(observed["usableAcceleration"])
        self.assertFalse(observed["benchmarkMeasured"])
        self.assertFalse(observed["aiServiceConnected"])
        self.assertFalse(observed["processIdentityAuthenticated"])
        self.assertEqual(
            self.requests,
            [("GET", "/api/version"), ("GET", "/api/tags"), ("GET", "/api/ps")],
        )

    def test_actual_ipv6_loopback_listener_is_distinguished(self):
        if not socket.has_ipv6:
            self.skipTest("IPv6 unavailable")
        with socket.socket(socket.AF_INET6) as listener:
            try:
                listener.bind(("::1", 0))
                listener.listen()
            except OSError:
                self.skipTest("IPv6 loopback unavailable")
            self.assertIn(
                "::1", local_listeners.loopback_bindings(listener.getsockname()[1])
            )

    def test_unknown_wildcard_and_nonlocal_bindings_reject_before_http(self):
        backend = "windows_rows" if os.name == "nt" else "linux_rows"
        for address in ("0.0.0.0", "::", "192.168.1.2"):
            with (
                patch.object(
                    local_listeners, backend, return_value=[(address, self.port)]
                ),
                self.assertRaisesRegex(ValueError, "E_OLLAMA_BINDING"),
            ):
                runtime.probe(self.port)
        self.assertEqual(self.requests, [])

    def test_real_probe_and_confirmation_survive_reload_without_runtime_changes(self):
        approve = Mock(return_value=True)
        outcome = runtime.select(self.target, self.port, review=approve)
        self.assertTrue(outcome["runtimeSelected"])
        self.assertFalse(outcome["selection"]["externalRuntimeManaged"])
        self.assertFalse(outcome["selection"]["aiServiceConnected"])
        self.assertEqual(len(self.requests), 6)
        state = load_installation(self.target).state
        self.assertEqual(runtime.selection(state), outcome["selection"])
        self.assertNotIn("models", outcome["selection"])
        self.assertTrue(runtime.status(self.target)["observation"]["available"])
        self.assertTrue(all(method == "GET" for method, _ in self.requests))

    def test_declined_selection_leaves_journal_byte_identical(self):
        before = self.installation.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_CANCELLED"):
            runtime.select(self.target, self.port, review=lambda _: False)
        self.assertEqual(self.installation.path.read_bytes(), before)

    def test_runtime_disappears_but_selection_is_retained_without_false_health(self):
        runtime.select(self.target, self.port, review=lambda _: True)
        before = self.installation.path.read_bytes()
        self.server.shutdown()
        self.server.server_close()
        result = runtime.status(self.target)
        self.assertTrue(result["runtimeSelected"])
        self.assertFalse(result["observation"]["available"])
        self.assertFalse(result["selectionMatchesCurrent"])
        self.assertFalse(result["aiServiceConnected"])
        self.assertEqual(self.installation.path.read_bytes(), before)

    def test_changed_version_or_model_is_visible_without_reselecting(self):
        runtime.select(self.target, self.port, review=lambda _: True)
        self.model["digest"] = "b" * 64
        result = runtime.status(self.target)
        self.assertTrue(result["observation"]["available"])
        self.assertFalse(result["selectionMatchesCurrent"])

    def test_changed_catalog_after_review_is_not_selected(self):
        def approve(_summary):
            self.model["digest"] = "b" * 64
            return True

        before = self.installation.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_CHANGED"):
            runtime.select(self.target, self.port, review=approve)
        self.assertEqual(self.installation.path.read_bytes(), before)

    def test_malformed_sizes_duplicate_names_and_unknown_vram_fail_closed(self):
        for changed in (
            {"size": True},
            {"size": -1},
            {"digest": "unknown"},
            {"name": "\x1bsecret"},
        ):
            with (
                self.subTest(changed=changed),
                self.assertRaisesRegex(ValueError, "E_OLLAMA_PROTOCOL"),
            ):
                runtime.model_rows({"models": [{**self.model, **changed}]})
        with self.assertRaisesRegex(ValueError, "E_OLLAMA_PROTOCOL"):
            runtime.model_rows({"models": [self.model, self.model]})
        observed = runtime.model_rows({"models": [self.model]}, running=True)
        self.assertIsNone(observed[0]["vramBytesObserved"])

    def test_redirect_oversize_duplicate_json_never_select(self):
        for mode in ("redirect", "oversize", "duplicate"):
            self.mode = mode
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(ValueError, "E_OLLAMA_PROTOCOL"),
            ):
                runtime.probe(self.port)
        self.assertNotIn("ollamaRuntime", load_installation(self.target).state)

    def test_stalled_real_http_is_cut_off_by_wall_clock_deadline(self):
        self.mode = "hang"
        started = time.monotonic()
        with (
            patch.object(runtime, "REQUEST_SECONDS", 0.2),
            self.assertRaisesRegex(ValueError, "E_OLLAMA_PROTOCOL"),
        ):
            runtime.probe(self.port)
        self.assertLess(time.monotonic() - started, 1.5)

    def test_dripping_real_headers_do_not_reset_absolute_deadline(self):
        self.mode = "drip"
        started = time.monotonic()
        with (
            patch.object(runtime, "REQUEST_SECONDS", 0.2),
            self.assertRaisesRegex(ValueError, "E_OLLAMA_PROTOCOL"),
        ):
            runtime.probe(self.port)
        self.assertLess(time.monotonic() - started, 1.5)

    def test_update_restore_and_retirement_fences_precede_network(self):
        for changes in (
            {"preparedForRestore": True},
            {"authority": {"phase": "retired"}},
            {"updateTransaction": {"phase": "migrating"}},
        ):
            state = copy.deepcopy(self.installation.state)
            self.installation.state.update(changes)
            self.installation.save()
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                runtime.select(self.target, self.port, review=lambda _: True)
            self.installation.state = state
            self.installation.save()
        self.assertEqual(self.requests, [])
