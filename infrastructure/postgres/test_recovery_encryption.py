"""Synthetic GnuPG round trip and failure checks; never reads personal backups."""

import hashlib
import io
import secrets
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("gpg"), "GnuPG is required")
class RecoveryEncryptionTest(unittest.TestCase):
    def test_synthetic_roundtrip_wrong_passphrase_and_tamper(self):
        with tempfile.TemporaryDirectory(prefix="ky005-synthetic-gpg-") as directory:
            root = Path(directory)
            home = root / "gnupg"
            home.mkdir(mode=0o700)
            password = secrets.token_hex(32).encode() + b"\n"
            source = root / "synthetic.tar"
            payload = b"Synthetic recovery fixture only.\n"
            with tarfile.open(source, "w") as archive:
                member = tarfile.TarInfo("synthetic/example.txt")
                member.size = len(payload)
                member.mode = 0o600
                archive.addfile(member, io.BytesIO(payload))
            encrypted = root / "synthetic.tar.gpg"
            command = [
                shutil.which("gpg"),
                "--no-options",
                "--homedir",
                str(home),
                "--batch",
                "--pinentry-mode",
                "loopback",
                "--no-symkey-cache",
                "--passphrase-fd",
                "0",
            ]

            def run(args, password_bytes=password):
                return subprocess.run(
                    command + args,
                    input=password_bytes,
                    capture_output=True,
                    timeout=45,
                    check=False,
                )

            try:
                result = run(
                    [
                        "--cipher-algo",
                        "AES256",
                        "--output",
                        str(encrypted),
                        "--symmetric",
                        str(source),
                    ]
                )
                self.assertEqual(result.returncode, 0)
                clear = root / "verified.tar"
                result = run(["--output", str(clear), "--decrypt", str(encrypted)])
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    hashlib.sha256(clear.read_bytes()).digest(),
                    hashlib.sha256(source.read_bytes()).digest(),
                )
                with tarfile.open(clear) as archive:
                    self.assertEqual(
                        archive.extractfile("synthetic/example.txt").read(), payload
                    )
                result = run(
                    [
                        "--output",
                        str(root / "wrong.unverified"),
                        "--decrypt",
                        str(encrypted),
                    ],
                    b"not-the-synthetic-password\n",
                )
                self.assertNotEqual(result.returncode, 0)
                damaged = bytearray(encrypted.read_bytes())
                damaged[-25] ^= 1
                corrupt = root / "corrupt.gpg"
                corrupt.write_bytes(damaged)
                result = run(
                    [
                        "--output",
                        str(root / "corrupt.unverified"),
                        "--decrypt",
                        str(corrupt),
                    ]
                )
                self.assertNotEqual(result.returncode, 0)
                # GPG may emit unverified plaintext before reporting integrity failure.
                # Failed outputs stay in scratch and are never promoted/extracted.
            finally:
                if shutil.which("gpgconf"):
                    subprocess.run(
                        ["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
