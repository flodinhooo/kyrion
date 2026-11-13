"""Authenticated image import without changing shared Docker/OCI references."""

from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

from bundle import unique_object

ROLES = {"core", "web", "postgres", "caddy"}
REFERENCE_ANNOTATIONS = {
    "org.opencontainers.image.ref.name",
    "io.containerd.image.name",
}
TAGGED_LINES = {
    "postgres": "    image: postgres:17.6-alpine",
    "core": '    image: "kyrion/core:${KYRION_RELEASE:?KYRION_RELEASE is required}"',
    "web": '    image: "kyrion/web:${KYRION_RELEASE:?KYRION_RELEASE is required}"',
    "caddy": "    image: caddy:2.10.2-alpine",
}


def image_set(images: dict) -> None:
    if (
        not isinstance(images, dict)
        or set(images) != ROLES
        or any(
            not isinstance(value, str)
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", value)
            for value in images.values()
        )
    ):
        raise ValueError("E_IMAGE_PIN")


def pin_compose(text: str, images: dict, original: dict | None = None) -> str:
    image_set(images)
    if original is not None:
        image_set(original)
    for role, tagged in TAGGED_LINES.items():
        old = tagged
        if old not in text.splitlines() and original is not None:
            old = "    image: " + original[role]
        if text.splitlines().count(old) != 1 or old + "\n" not in text:
            raise ValueError("E_UPDATE_COMPOSE_LAYOUT")
        text = text.replace(old + "\n", "    image: " + images[role] + "\n", 1)
    return text


def scrub_names(name: str, raw: bytes) -> bytes:
    value = json.loads(raw, object_pairs_hook=unique_object)
    if name == "manifest.json":
        if (
            not isinstance(value, list)
            or len(value) != 1
            or not isinstance(value[0], dict)
        ):
            raise ValueError("E_IMAGE")
        value[0]["RepoTags"] = []
    elif name == "repositories":
        if not isinstance(value, dict):
            raise ValueError("E_IMAGE")
        value = {}
    else:
        if (
            not isinstance(value, dict)
            or type(value.get("schemaVersion")) is not int
            or value["schemaVersion"] != 2
            or not isinstance(value.get("manifests"), list)
            or not 1 <= len(value["manifests"]) <= 16
        ):
            raise ValueError("E_IMAGE")
        for descriptor in (value, *value["manifests"]):
            if not isinstance(descriptor, dict):
                raise TypeError("E_IMAGE")
            annotations = descriptor.get("annotations", {})
            if not isinstance(annotations, dict):
                raise TypeError("E_IMAGE")
            for key in REFERENCE_ANNOTATIONS:
                annotations.pop(key, None)
    return json.dumps(value, separators=(",", ":")).encode()


def archive_references(archive: Path, expected: str, architecture: str) -> list[str]:
    """Bind OCI manifest/index IDs to the authenticated configuration witness.

    Classic engines expose the configuration digest as image ID. Containerd
    stores can expose its enclosing index. Neither is accepted without a digest
    path to the same reviewed configuration and target platform.
    """
    references = [expected]
    with tarfile.open(archive) as package:
        names = package.getnames()
        if "index.json" not in names:
            return references

        def read(name):
            if names.count(name) != 1:
                raise ValueError("E_IMAGE")
            member = package.getmember(name)
            if not member.isfile() or not 0 < member.size <= 1024**2:
                raise ValueError("E_IMAGE")
            return package.extractfile(member).read()

        visited = set()

        def follow(descriptor, depth=0, top=False):
            if not isinstance(descriptor, dict) or depth > 4 or len(visited) > 64:
                raise ValueError("E_IMAGE")
            annotations = descriptor.get("annotations", {})
            if not isinstance(annotations, dict) or (
                not top and REFERENCE_ANNOTATIONS & set(annotations)
            ):
                raise ValueError("E_IMAGE")
            platform = descriptor.get("platform")
            unknown_platform = False
            if platform is not None:
                if not isinstance(platform, dict):
                    raise ValueError("E_IMAGE")
                if (
                    platform.get("os") == "unknown"
                    and platform.get("architecture") == "unknown"
                ):
                    unknown_platform = True
                elif (
                    platform.get("os") != "linux"
                    or platform.get("architecture") != architecture
                ):
                    raise ValueError("E_IMAGE")
            digest = descriptor.get("digest")
            if not isinstance(digest, str) or not re.fullmatch(
                r"sha256:[a-f0-9]{64}", digest
            ):
                raise ValueError("E_IMAGE")
            visited.add(digest)
            raw = read("blobs/sha256/" + digest.removeprefix("sha256:"))
            if (
                hashlib.sha256(raw).hexdigest() != digest.removeprefix("sha256:")
                or type(descriptor.get("size")) is not int
                or descriptor["size"] != len(raw)
            ):
                raise ValueError("E_IMAGE")
            value = json.loads(raw, object_pairs_hook=unique_object)
            if (
                not isinstance(value, dict)
                or type(value.get("schemaVersion")) is not int
                or value["schemaVersion"] != 2
            ):
                raise ValueError("E_IMAGE")
            if "manifests" in value:
                if unknown_platform or descriptor.get("mediaType") not in {
                    "application/vnd.oci.image.index.v1+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json",
                }:
                    raise ValueError("E_IMAGE")
                children = value["manifests"]
                if not isinstance(children, list) or not 1 <= len(children) <= 16:
                    raise ValueError("E_IMAGE")
                bindings = [follow(child, depth + 1) for child in children]
                bound = any(bindings)
            else:
                if descriptor.get("mediaType") not in {
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.docker.distribution.manifest.v2+json",
                }:
                    raise ValueError("E_IMAGE")
                configuration = value.get("config")
                if (
                    not isinstance(configuration, dict)
                    or not isinstance(configuration.get("digest"), str)
                    or not re.fullmatch(r"sha256:[a-f0-9]{64}", configuration["digest"])
                ):
                    raise ValueError("E_IMAGE")
                config_digest = configuration["digest"].removeprefix("sha256:")
                raw_config = read("blobs/sha256/" + config_digest)
                if (
                    type(configuration.get("size")) is not int
                    or configuration["size"] != len(raw_config)
                    or configuration.get("mediaType")
                    not in {
                        "application/vnd.oci.image.config.v1+json",
                        "application/vnd.docker.container.image.v1+json",
                        "application/vnd.oci.empty.v1+json",
                    }
                ):
                    raise ValueError("E_IMAGE")
                if hashlib.sha256(raw_config).hexdigest() != config_digest:
                    raise ValueError("E_IMAGE")
                config = json.loads(raw_config, object_pairs_hook=unique_object)
                layers = value.get("layers")
                attestation = isinstance(config, dict) and (
                    (
                        config.get("os") == "unknown"
                        and config.get("architecture") == "unknown"
                    )
                    or (
                        config == {}
                        and value.get("artifactType")
                        == "application/vnd.docker.attestation.manifest.v1+json"
                        and configuration["mediaType"]
                        == "application/vnd.oci.empty.v1+json"
                    )
                )
                if attestation and (platform is None or unknown_platform):
                    if (
                        not isinstance(layers, list)
                        or not 1 <= len(layers) <= 16
                        or any(
                            not isinstance(layer, dict)
                            or layer.get("mediaType") != "application/vnd.in-toto+json"
                            or not isinstance(layer.get("digest"), str)
                            or not re.fullmatch(r"sha256:[a-f0-9]{64}", layer["digest"])
                            or type(layer.get("size")) is not int
                            or not 0 < layer["size"] <= 80 * 1024**2
                            for layer in layers
                        )
                    ):
                        raise ValueError("E_IMAGE")
                    return False  # Metadata only; never an executable image ID.
                if (
                    not isinstance(config, dict)
                    or unknown_platform
                    or configuration["digest"] != expected
                    or configuration["mediaType"] == "application/vnd.oci.empty.v1+json"
                    or config.get("os") != "linux"
                    or config.get("architecture") != architecture
                ):
                    raise ValueError("E_IMAGE")
                bound = True
            if bound and digest not in references:
                references.append(digest)
            return bound

        index = json.loads(read("index.json"), object_pairs_hook=unique_object)
        if (
            not isinstance(index, dict)
            or type(index.get("schemaVersion")) is not int
            or index["schemaVersion"] != 2
            or not isinstance(index.get("manifests"), list)
            or not 1 <= len(index["manifests"]) <= 16
        ):
            raise ValueError("E_IMAGE")
        bindings = [follow(item, top=True) for item in index["manifests"]]
        if not any(bindings):
            raise ValueError("E_IMAGE")
    return references


def load_untagged(
    root: Path, archive: Path, expected: str, architecture: str, run
) -> str:
    """Caller authenticates/validates the original archive before this operation."""
    from recovery import private_restore_directory

    if not re.fullmatch(r"sha256:[a-f0-9]{64}", expected) or architecture not in {
        "amd64",
        "arm64",
    }:
        raise ValueError("E_IMAGE_PIN")
    references = archive_references(archive, expected, architecture)
    with private_restore_directory(root, None) as scratch:
        rewritten = scratch / "image.tar"
        seen = set()
        with (
            tarfile.open(archive, "r|") as source,
            tarfile.open(rewritten, "w") as target,
        ):
            for count, member in enumerate(source, start=1):
                if count > 4096:
                    raise ValueError("E_IMAGE")
                if member.name in {"manifest.json", "index.json", "repositories"}:
                    if (
                        not member.isfile()
                        or member.size > 1024**2
                        or member.name in seen
                    ):
                        raise ValueError("E_IMAGE")
                    seen.add(member.name)
                    raw = scrub_names(member.name, source.extractfile(member).read())
                    member.size = len(raw)
                    target.addfile(member, io.BytesIO(raw))
                else:
                    target.addfile(
                        member, source.extractfile(member) if member.isfile() else None
                    )
        if "manifest.json" not in seen:
            raise ValueError("E_IMAGE")
        run("load", "--input", str(rewritten), timeout=600)
    for reference in references:
        try:
            loaded = json.loads(run("image", "inspect", reference))[0]
        except (ValueError, OSError):
            continue
        if (
            loaded.get("Id") not in references
            or loaded.get("Os") != "linux"
            or loaded.get("Architecture") != architecture
        ):
            raise ValueError("E_IMAGE")
        return loaded["Id"]
    raise ValueError("E_IMAGE")
