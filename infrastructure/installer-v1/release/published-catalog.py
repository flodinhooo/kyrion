"""Generate website download metadata only after verified public publication.

Read-only GitHub API access. This command does not create or publish a release.
The native artifact metadata must be accepted and signed by the release owner.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_policy import NoRedirect, version
from runtime import atomic_json

REPOSITORY = "https://github.com/flodinhooo/kyrion"


class PublicationError(ValueError):
    pass


def published_record(metadata: dict, release: dict) -> dict:
    selected_version = metadata.get("version")
    version(selected_version)
    platform = metadata.get("platform")
    if (
        metadata.get("schemaVersion") != 1
        or platform not in {"windows-amd64", "linux-amd64", "linux-arm64"}
        or metadata.get("nativeSmokeTest") is not True
        or metadata.get("embeddedVersionVerified") is not True
        or metadata.get("platformInstallationAccepted") is not True
        or type(metadata.get("bytes")) is not int
        or metadata["bytes"] <= 0
        or not isinstance(metadata.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"])
        or not isinstance(metadata.get("file"), str)
        or not re.fullmatch(r"[A-Za-z0-9._-]+", metadata["file"])
    ):
        raise ValueError("E_PUBLICATION_ACCEPTANCE")
    if (
        release.get("draft") is not False
        or release.get("tag_name") != "v" + selected_version
    ):
        raise PublicationError("E_NOT_PUBLISHED")
    if not metadata["file"].endswith(
        ".exe" if platform == "windows-amd64" else ".tar.gz"
    ):
        raise ValueError("E_PUBLISHED_ASSET")
    published = release.get("published_at")
    if not isinstance(published, str):
        raise PublicationError("E_NOT_PUBLISHED")
    timestamp = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp > datetime.datetime.now(
        datetime.timezone.utc
    ):
        raise PublicationError("E_NOT_PUBLISHED")
    url = (
        REPOSITORY + "/releases/download/v" + selected_version + "/" + metadata["file"]
    )
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise PublicationError("E_NOT_PUBLISHED")
    matches = [asset for asset in assets if asset.get("name") == metadata["file"]]
    if len(matches) != 1:
        raise ValueError("E_PUBLISHED_ASSET")
    asset = matches[0]
    if (
        asset.get("state") != "uploaded"
        or asset.get("browser_download_url") != url
        or asset.get("size") != metadata["bytes"]
        or asset.get("digest") != "sha256:" + metadata["sha256"]
    ):
        raise ValueError("E_PUBLISHED_ASSET")
    return {
        "version": selected_version,
        "platform": platform,
        "url": url,
        "bytes": metadata["bytes"],
        "sha256": metadata["sha256"],
        "publishedAt": published,
        "notesUrl": REPOSITORY + "/releases/tag/v" + selected_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, action="append", required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verified = []
    for path in args.metadata:
        if path.is_symlink() or path.stat().st_size > 16384:
            raise ValueError("E_PUBLICATION_METADATA")
        signature = path.with_suffix(path.suffix + ".sig")
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-rawin",
                "-pubin",
                "-inkey",
                str(args.public_key),
                "-in",
                str(path),
                "-sigfile",
                str(signature),
            ],
            capture_output=True,
            check=True,
            timeout=15,
        )
        verified.append(json.loads(path.read_text(encoding="utf-8")))
    selected_version = verified[0]["version"]
    version(selected_version)
    if any(metadata["version"] != selected_version for metadata in verified):
        raise ValueError("E_PUBLICATION_VERSION")
    request = urllib.request.Request(
        "https://api.github.com/repos/flodinhooo/kyrion/releases/tags/v"
        + selected_version,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Kyrion-release-verifier",
        },
    )
    with urllib.request.build_opener(NoRedirect()).open(
        request, timeout=20
    ) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
        if response.status != 200 or len(raw) > 2 * 1024 * 1024:
            raise ValueError("E_PUBLICATION_RESPONSE")
        release = json.loads(raw)
    records = [published_record(metadata, release) for metadata in verified]
    if len({(record["version"], record["platform"]) for record in records}) != len(
        records
    ):
        raise ValueError("E_PUBLICATION_DUPLICATE")
    # Publishing the website remains a separate operation. This only prepares
    # its checked source catalog after actual remote assets have been verified.
    atomic_json(args.output, {"schemaVersion": 1, "releases": records})


if __name__ == "__main__":
    main()
