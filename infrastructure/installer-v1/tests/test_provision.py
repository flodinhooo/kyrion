"""Injected Compose orchestration; never touches Docker or existing host data."""

import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle
import runtime


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "installation"
        self.release = self.root / "release"
        self.release.mkdir()
        self.manifest = {
            "schemaVersion": 1,
            "release": "1.2.3",
            "architecture": "linux/arm64",
            "artifacts": [],
        }
        for name in (
            "kyrion-core-arm64.tar",
            "kyrion-web-arm64.tar",
            "postgres-arm64.tar",
            "caddy-arm64.tar",
        ):
            path = self.release / name
            path.write_bytes(b"synthetic image fixture")
            self.manifest["artifacts"].append(
                {
                    "name": name,
                    "bytes": path.stat().st_size,
                    "sha256": bundle.sha256(path),
                }
            )
        (self.release / "manifest.json").write_text(json.dumps(self.manifest))
        self.digest = bundle.sha256(self.release / "manifest.json")
        self.observed = {
            "candidateProvisioning": True,
            "ramBytes": 8 * 1024**3,
            "freeBytes": 30 * 1024**3,
            "architecture": "arm64",
        }
        self.commands = []

    def command(self, args, timeout=120):
        self.commands.append(args)
        if args[:3] == ["docker", "image", "inspect"]:
            return json.dumps(
                [{"Id": "sha256:fixture", "Os": "linux", "Architecture": "arm64"}]
            )
        return ""

    @staticmethod
    def configure(installation):
        installation.write("secrets/test.key", b"first fixture credential")
        installation.state["stage"] = "configured"
        installation.save()

    @staticmethod
    def start(installation):
        installation.state["stage"] = "services-healthy"
        installation.save()

    def provision(self, start=None, identity=None):
        with (
            patch("runtime.validate_inputs"),
            patch("runtime.inventory", return_value=self.observed),
            patch("runtime.os.geteuid", return_value=0, create=True),
            patch(
                "runtime.installation_lock",
                side_effect=lambda target: contextlib.nullcontext(),
            ),
            patch(
                "runtime.authenticated_review",
                return_value=bundle.ReviewedBundle(self.manifest, self.digest),
            ),
            patch("runtime.runtime_checks"),
            patch(
                "runtime.image_identity",
                side_effect=identity or (lambda *_args: "sha256:fixture"),
            ),
            patch("runtime.execute", side_effect=self.command),
            patch.object(runtime.Installation, "configure", self.configure),
            patch.object(runtime.Installation, "start", start or self.start),
        ):
            return runtime.provision(
                self.target,
                self.release,
                self.root / "public.pem",
                "kyrion.home.arpa",
                "192.168.1.2",
                self.digest,
            )

    def test_fresh_run_preserves_unrelated_files_and_loads_only_declared_images(self):
        sentinel = self.root / "unrelated"
        sentinel.write_bytes(b"preserve")
        state = self.provision()
        self.assertEqual(state["stage"], "services-healthy")
        loads = [args for args in self.commands if args[:2] == ["docker", "load"]]
        self.assertEqual(len(loads), 4)
        self.assertTrue(
            all(
                Path(command[3]).is_relative_to(self.target / "release-input")
                for command in loads
            )
        )
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        self.assertEqual(state["ownerSetup"], "not-verified")

    def test_original_download_changes_cannot_reach_docker_load(self):
        def identity(_path, _tag):
            for item in self.manifest["artifacts"]:
                (self.release / item["name"]).write_bytes(b"mutated external download")
            return "sha256:fixture"

        self.provision(identity=identity)
        for item in self.manifest["artifacts"]:
            self.assertEqual(
                bundle.sha256(self.target / "release-input" / item["name"]),
                item["sha256"],
            )
        self.assertTrue(
            all(
                str(self.target / "release-input") in command[3]
                for command in self.commands
                if command[:2] == ["docker", "load"]
            )
        )

    def test_interrupted_public_staging_preserves_partial_and_resumes(self):
        def interrupt(_source, destination, _expected):
            destination.write_bytes(b"partial archive bytes")
            raise OSError("synthetic staging interruption")

        with (
            patch("runtime.copy_image_input", side_effect=interrupt),
            self.assertRaises(OSError),
        ):
            self.provision()
        self.assertFalse(
            any(command[:2] == ["docker", "load"] for command in self.commands)
        )
        self.commands.clear()
        state = self.provision()
        self.assertEqual(len(state["imageStaging"]["preserved"]), 1)
        preserved = (
            self.target / "release-input" / state["imageStaging"]["preserved"][0]
        )
        self.assertEqual(preserved.read_bytes(), b"partial archive bytes")
        self.assertEqual(
            len(
                [
                    command
                    for command in self.commands
                    if command[:2] == ["docker", "load"]
                ]
            ),
            4,
        )

    def test_runtime_failure_retains_machine_code_and_secret(self):
        def fail(installation):
            raise ValueError("E_CORE: synthetic failure")

        with self.assertRaisesRegex(ValueError, "E_CORE"):
            self.provision(start=fail)
        state = json.loads((self.target / "install-state.json").read_text())
        self.assertEqual(state["lastError"], "E_CORE")
        self.assertEqual(
            (self.target / "secrets/test.key").read_bytes(), b"first fixture credential"
        )

    def test_wrong_architecture_stops_before_loading_or_creating_target(self):
        self.observed["architecture"] = "amd64"
        with self.assertRaisesRegex(ValueError, "E_RELEASE"):
            self.provision()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.commands)

    def test_unknown_memory_is_not_invented(self):
        self.observed["ramBytes"] = None
        with self.assertRaisesRegex(ValueError, "E_MEMORY"):
            self.provision()
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
