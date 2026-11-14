"""Actual public HTTPS in a marked minimal Debian root with no system CAs."""

import argparse
import hashlib
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, "/opt/kyrion-installer")
import public_https
import release_policy


def main(worker: Path | None = None):
    marker = json.loads(Path("/etc/kyrion-crypto-package-fixture.json").read_bytes())
    identity = Path("/").stat()
    if (
        os.geteuid() != 0
        or marker.get("scope") != "installer-crypto-package-development-fixture"
        or marker.get("purpose") != "transport"
        or marker.get("rootDevice") != identity.st_dev
        or marker.get("rootInode") != identity.st_ino
    ):
        raise ValueError("E_TEST_ENVIRONMENT")
    ordinary = ssl.create_default_context()
    assert ordinary.cert_store_stats()["x509_ca"] == 0
    assert not ssl.get_default_verify_paths().cafile
    url = "https://pypi.org/pypi/certifi/2026.10.23/json"
    try:
        urllib.request.urlopen(url, context=ordinary, timeout=30)
    except urllib.error.URLError as error:
        assert isinstance(error.reason, ssl.SSLCertVerificationError)
    else:
        raise AssertionError("System trust unexpectedly accepted the connection")
    document = json.loads(release_policy.fetch_document(url))
    assert document["info"]["version"] == "2026.10.23"
    status = public_https.status()
    assert status["trustSource"] == "bundled"
    assert status["certificateVerificationRequired"]
    assert status["hostnameVerificationRequired"]
    report = {
        "scope": "installer-public-https-development-fixture",
        "systemCaCertificatesBefore": 0,
        "ordinaryHttpsRejectedCertificate": True,
        "verifiedPublicMetadataDownloaded": True,
        "publicMetadataVersion": document["info"]["version"],
        "releaseSignatureAcceptanceTested": False,
        "nativeExecutableTested": False,
        "trust": status,
    }
    if worker is not None:
        if worker != Path("/opt/native-installer") or worker.is_symlink():
            raise ValueError("E_TEST_WORKER")
        native = subprocess.run(
            [str(worker), "--capabilities"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        native_trust = json.loads(native.stdout)["publicHttpsTrust"]
        assert native_trust == status
        report.update(
            {
                "nativeExecutableTested": True,
                "nativeWorkerSha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
                "nativeHttpsConnectionTested": False,
            }
        )
    Path("/work/report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    main(parser.parse_args().worker)
