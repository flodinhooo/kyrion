"""Authenticate a bounded development bundle with an ephemeral in-memory key.

Never uses a production key or changes publication/signing acceptance metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_bundle import validate


def sign(root: Path) -> dict:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    validate(root)
    if (root / "manifest.sig").exists() or (root / "test-public.pem").exists():
        raise ValueError("E_NATIVE_EXISTING_SIGNATURE")
    manifest = (root / "manifest.json").read_bytes()
    key = Ed25519PrivateKey.generate()
    with (root / "manifest.sig").open("xb") as output:
        output.write(key.sign(manifest))
    with (root / "test-public.pem").open("xb") as output:
        output.write(
            key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    return {
        "developmentSignature": True,
        "productionReleaseAccepted": False,
        "privateKeyPersisted": False,
        "manifestSha256": hashlib.sha256(manifest).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(sign(args.bundle)))
