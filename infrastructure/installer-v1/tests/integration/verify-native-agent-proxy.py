"""Actual native Caddy validation only; no SCM, server or household action."""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bundle import sha256
from crypto_support import certificate, private_tls_key
from host import reject_links
from native_bundle import authenticated_review
from native_proxy import configuration
from node_ingress_native import NativeRuntime


def exercise(args):
    if os.name != "nt":
        raise ValueError("E_WINDOWS_FIXTURE_PLATFORM")
    reviewed = authenticated_review(args.bundle, args.key)
    name = "runtime/caddy/caddy.exe"
    row = next(row for row in reviewed.manifest["files"] if row["path"] == name)
    source = args.profile / name
    reject_links(source)
    if source.stat().st_size != row["bytes"] or sha256(source) != row["sha256"]:
        raise ValueError("E_NATIVE_FIXTURE_PROFILE_INTEGRITY")
    with tempfile.TemporaryDirectory(prefix="kyrion-caddy-validation-") as directory:
        root = Path(directory)
        target = root / "payload" / name
        target.parent.mkdir(parents=True)
        shutil.copyfile(source, target)
        tls = root / "data/tls"
        tls.mkdir(parents=True)
        key = private_tls_key()
        (tls / "key.pem").write_bytes(key)
        public = certificate("localhost", "127.0.0.1", key)
        for path in (tls / "cert.pem", root / "core-cert.pem", root / "web-cert.pem"):
            path.write_bytes(public)
        config = {
            "hostname": "localhost",
            "address": "127.0.0.1",
            "ports": {"core": 18080, "web": 13000, "caddy": 14443},
        }
        # Only the lifecycle adapter's real CLI-validation method is exercised.
        # This does not skip and then claim installed-service preconditions.
        adapter = NativeRuntime.__new__(NativeRuntime)
        adapter.installation = SimpleNamespace(target=root)
        for agent in (False, True):
            adapter.validate(configuration(root, config, agent=agent))
        try:
            adapter.validate("synthetic invalid caddy configuration {{{\n")
        except ValueError as error:
            if str(error) != "E_AGENT_INGRESS_RUNTIME":
                raise
        else:
            raise ValueError("E_FIXTURE_INVALID_PROXY_ACCEPTED")
    return {
        "actualNativeCaddyCli": True,
        "caddySha256": row["sha256"],
        "managedLegacyAndAgentDefinitionsValidated": True,
        "invalidConfigurationRejected": True,
        "servicesOrTasksRegistered": False,
        "serverStarted": False,
        "realHouseholdActions": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "key", "profile", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = exercise(args)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
