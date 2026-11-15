"""Native policy plus real private Windows files/DPAPI; SCM is explicitly mocked."""

import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import node_ingress
from authority import pending_ingress_format, require_active
from native_proxy import configuration
from node_ingress_native import role_allowed
from recovery import load_installation
from runtime import Installation


class NativeIngressPolicyTests(unittest.TestCase):
    def test_pending_format_requires_exact_versions_and_an_active_phase(self):
        state = {
            "formatVersion": 2,
            "agentIngressTransition": {"formatVersion": 1, "phase": "published"},
        }
        self.assertTrue(pending_ingress_format(state))
        self.assertFalse(pending_ingress_format({**state, "formatVersion": True}))
        for value in (
            None,
            {},
            {"formatVersion": True, "phase": "published"},
            {"formatVersion": 1, "phase": "verified"},
        ):
            self.assertFalse(
                pending_ingress_format({**state, "agentIngressTransition": value})
            )

    def test_scm_role_exception_never_starts_core_during_new_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / node_ingress.FILE).write_bytes(b"synthetic approved configuration")
            digest = node_ingress.digest("synthetic approved configuration")
            transaction = {
                "phase": "published",
                "beforeSha256": digest,
                "afterSha256": digest,
            }
            state = {
                "formatVersion": 2,
                "backend": "windows-native",
                "configuration": {},
                "files": {node_ingress.FILE: digest},
                node_ingress.KEY: {"formatVersion": 1, "phase": "published"},
            }
            with patch("node_ingress_native.transition", return_value=transaction):
                self.assertTrue(role_allowed(root, state, "caddy"))
                for role in ("core", "web", "postgres-init"):
                    with (
                        self.subTest(role=role),
                        self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_PENDING"),
                    ):
                        role_allowed(root, state, role)
                state[node_ingress.KEY]["phase"] = transaction["phase"] = "restored"
                for role in ("core", "web", "caddy"):
                    self.assertTrue(role_allowed(root, state, role))
                for fence in (
                    {"authority": {"phase": "retired"}},
                    {"preparedForRestore": True},
                ):
                    with self.assertRaisesRegex(ValueError, "E_AUTHORITY_INACTIVE"):
                        role_allowed(root, {**state, **fence}, "caddy")
                (root / node_ingress.FILE).write_bytes(b"unapproved configuration")
                with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_CUSTOM"):
                    role_allowed(root, state, "caddy")

    def test_managed_native_definition_retains_tls_and_exact_bind(self):
        config = {
            "hostname": "fixture.test",
            "address": "127.0.0.1",
            "ports": {"caddy": 14443, "core": 18080, "web": 13000},
        }
        root = Path(tempfile.gettempdir()).resolve() / "kyrion-public-fixture"
        current = configuration(root, config)
        legacy = configuration(root, config, agent=False)
        self.assertIn("https://fixture.test:14443 {\n bind 127.0.0.1\n", current)
        self.assertIn("https://127.0.0.1:18080", current)
        self.assertIn("/v1/gateway-agent/tasks", current)
        self.assertIn("tls_trust_pool file", current)
        self.assertNotIn("tls_insecure_skip_verify", current)
        self.assertNotIn("gateway-agent", legacy)
        self.assertIn("reverse_proxy https://127.0.0.1:13000", legacy)


@unittest.skipUnless(
    os.name == "nt", "Actual private Windows file publication and DPAPI"
)
class NativeIngressFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kyrion-native-ingress-private-")
        self.addCleanup(temporary.cleanup)
        self.installation = Installation(
            Path(temporary.name) / "installed",
            {"release": "1.2.3", "architecture": "windows/amd64"},
            "a" * 64,
            "fixture.test",
            "127.0.0.1",
        )
        self.installation.state["backend"] = "windows-native"
        self.installation.write("installer.exe", b"synthetic worker, never executed")
        self.installation.write("native-manifest.json", "{}")
        self.config = {
            "formatVersion": 1,
            "hostname": "fixture.test",
            "address": "127.0.0.1",
            "ports": {"postgres": 15432, "core": 18080, "web": 13000, "caddy": 14443},
        }
        self.installation.write("native-runtime.json", json.dumps(self.config))
        self.before = configuration(self.installation.target, self.config, agent=False)
        self.installation.write(node_ingress.FILE, self.before)
        self.approval = {"actorId": str(uuid.uuid4()), "spaceId": str(uuid.uuid4())}
        # The user-owned fixture is not a native administrator/virtual-service
        # deployment. Exercise actual file/DPAPI behavior without granting one.
        self.enterContext(patch("native_runtime.permissions"))
        self.enterContext(patch("operational_restore.require_admin"))

    def test_actual_native_publication_resume_barrier_and_original_recovery(self):
        failed = Mock()
        failed.start.side_effect = RuntimeError("synthetic SCM failure")
        with self.assertRaises(RuntimeError):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=failed
            )
        state = self.installation.state
        self.assertEqual(state["formatVersion"], 2)
        self.assertEqual(state[node_ingress.KEY]["phase"], "published")
        self.assertTrue(role_allowed(self.installation.target, state, "caddy"))
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_PENDING"):
            require_active(state)
        with self.assertRaisesRegex(ValueError, "E_AGENT_INGRESS_PENDING"):
            load_installation(self.installation.target)
        loaded = load_installation(self.installation.target, verify=False)
        transaction = loaded.state[node_ingress.KEY]["id"]
        result = node_ingress.apply(loaded, None, "recover", runtime=Mock())
        self.assertEqual(result["phase"], "recovered")
        self.assertEqual((loaded.target / node_ingress.FILE).read_text(), self.before)
        self.assertEqual(loaded.state["formatVersion"], 1)
        self.assertEqual(loaded.state[node_ingress.KEY]["id"], transaction)
        self.assertEqual(loaded.state[node_ingress.KEY]["recoveredBy"], "os-admin")
        load_installation(loaded.target)

    def test_actual_native_resume_keeps_original_transaction_identity(self):
        failed = Mock()
        failed.start.side_effect = RuntimeError("synthetic SCM failure")
        with self.assertRaises(RuntimeError):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=failed
            )
        identity = self.installation.state[node_ingress.KEY]["id"]
        loaded = load_installation(self.installation.target, verify=False)
        result = node_ingress.apply(loaded, self.approval, "resume", runtime=Mock())
        self.assertEqual(result["phase"], "verified")
        self.assertEqual(loaded.state[node_ingress.KEY]["id"], identity)
        self.assertEqual(loaded.state["formatVersion"], 1)

    def test_failed_windows_security_creation_preserves_original_proxy(self):
        from windows_security import open_secured_file

        def fail_proxy_only(path, source):
            if path.name.startswith(".Caddyfile.ingress-"):
                raise OSError("synthetic native ACL failure")
            return open_secured_file(path, source)

        with (
            patch(
                "windows_security.open_secured_file",
                side_effect=fail_proxy_only,
            ),
            self.assertRaises(OSError),
        ):
            node_ingress.apply(
                self.installation, self.approval, "configure", runtime=Mock()
            )
        self.assertEqual(
            (self.installation.target / node_ingress.FILE).read_text(), self.before
        )
        self.assertEqual(self.installation.state[node_ingress.KEY]["phase"], "stopped")
