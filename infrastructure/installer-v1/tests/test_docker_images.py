"""Real OCI digest graphs and archive bytes; Docker calls are injected here."""

import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docker_images import archive_references, load_untagged, pin_compose, scrub_names


class DockerImages(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def archive(
        self,
        *,
        wrong_config=False,
        corrupt_blob=False,
        nested_name=False,
        root_attestation=False,
        executable_attestation=False,
    ):
        members = {}

        def blob(value, media):
            raw = json.dumps(value, separators=(",", ":")).encode()
            digest = hashlib.sha256(raw).hexdigest()
            members["blobs/sha256/" + digest] = raw
            return {"mediaType": media, "digest": "sha256:" + digest, "size": len(raw)}

        config = blob(
            {"os": "linux", "architecture": "amd64"},
            "application/vnd.oci.image.config.v1+json",
        )
        expected = config["digest"]
        selected = (
            blob(
                {
                    "os": "linux",
                    "architecture": "amd64",
                    "config": {"Labels": {"variant": "other"}},
                },
                "application/vnd.oci.image.config.v1+json",
            )
            if wrong_config
            else config
        )
        manifest = blob(
            {"schemaVersion": 2, "config": selected, "layers": []},
            "application/vnd.oci.image.manifest.v1+json",
        )
        manifest["platform"] = {"os": "linux", "architecture": "amd64"}
        if nested_name:
            manifest["annotations"] = {
                "io.containerd.image.name": "foreign/image:current"
            }
        parent = blob(
            {"schemaVersion": 2, "manifests": [manifest]},
            "application/vnd.oci.image.index.v1+json",
        )
        parent["annotations"] = {
            "io.containerd.image.name": "synthetic/image:1",
            "org.opencontainers.image.ref.name": "1",
            "org.opencontainers.image.licenses": "Apache-2.0",
        }
        roots = [parent]
        if root_attestation or executable_attestation:
            metadata = blob(
                {
                    "os": "linux" if executable_attestation else "unknown",
                    "architecture": "amd64" if executable_attestation else "unknown",
                    "config": {"Labels": {"fixture": "attestation"}},
                },
                "application/vnd.oci.image.config.v1+json",
            )
            attestation = blob(
                {
                    "schemaVersion": 2,
                    "config": metadata,
                    "layers": [
                        blob(
                            {"_type": "https://in-toto.io/Statement/v0.1"},
                            "application/vnd.in-toto+json",
                        )
                    ],
                },
                "application/vnd.oci.image.manifest.v1+json",
            )
            roots.append(attestation)
        members["index.json"] = json.dumps(
            {"schemaVersion": 2, "manifests": roots}
        ).encode()
        members["manifest.json"] = json.dumps(
            [
                {
                    "Config": "blobs/sha256/" + expected[7:],
                    "RepoTags": ["synthetic/image:1"],
                    "Layers": [],
                }
            ]
        ).encode()
        if corrupt_blob:
            members["blobs/sha256/" + expected[7:]] = b"{}"
        archive = self.root / "image.tar"
        with tarfile.open(archive, "w") as package:
            for name, raw in members.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(raw)
                package.addfile(entry, io.BytesIO(raw))
        return archive, expected, parent["digest"]

    def test_containerd_index_is_bound_to_same_reviewed_configuration(self):
        archive, expected, parent = self.archive()
        references = archive_references(archive, expected, "amd64")
        self.assertEqual(references[0], expected)
        self.assertIn(parent, references)

        def run(*args, **_options):
            if args[0] == "load":
                with tarfile.open(args[2]) as package:
                    index = json.load(package.extractfile("index.json"))
                    self.assertEqual(
                        index["manifests"][0]["annotations"],
                        {"org.opencontainers.image.licenses": "Apache-2.0"},
                    )
                return b"loaded"
            if args[-1] == expected:
                raise ValueError("E_IMAGE_NOT_FOUND")
            return json.dumps(
                [{"Id": parent, "Os": "linux", "Architecture": "amd64"}]
            ).encode()

        self.assertEqual(
            load_untagged(self.root, archive, expected, "amd64", run), parent
        )

    def test_wrong_configuration_corrupt_blob_and_nested_names_refuse_before_load(self):
        for option in ("wrong_config", "corrupt_blob", "nested_name"):
            archive, expected, _ = self.archive(**{option: True})
            run = Mock()
            with self.subTest(option=option), self.assertRaises(ValueError):
                load_untagged(self.root, archive, expected, "amd64", run)
            run.assert_not_called()

    def test_legacy_repository_mapping_is_removed(self):
        self.assertEqual(
            json.loads(scrub_names("repositories", b'{"shared":{"current":"layer"}}')),
            {},
        )

    def test_docker_save_attestation_without_descriptor_platform_is_not_executable(
        self,
    ):
        archive, expected, parent = self.archive(root_attestation=True)
        references = archive_references(archive, expected, "amd64")
        self.assertEqual(len(references), 3)
        self.assertIn(parent, references)
        archive, expected, _ = self.archive(executable_attestation=True)
        run = Mock()
        with self.assertRaises(ValueError):
            load_untagged(self.root, archive, expected, "amd64", run)
        run.assert_not_called()

    def test_owned_compose_pins_preserve_service_configuration_and_reject_unknown_layout(
        self,
    ):
        text = (Path(__file__).parents[1] / "templates/compose.yml").read_text(
            encoding="utf-8"
        )
        images = {
            role: "sha256:" + digit * 64
            for role, digit in zip(
                ("core", "web", "postgres", "caddy"), "abcd", strict=True
            )
        }
        pinned = pin_compose(text, images)
        self.assertIn("read_only: true", pinned)
        self.assertIn("depends_on:", pinned)
        self.assertNotIn("image: postgres:", pinned)
        self.assertEqual(pin_compose(pinned, images, images), pinned)
        with self.assertRaisesRegex(ValueError, "E_UPDATE_COMPOSE_LAYOUT"):
            pin_compose(
                text.replace(
                    "    image: postgres:17.6-alpine", "    image: operator/custom:1"
                ),
                images,
            )
