"""Actual crypto and TLS primitives, synthetic keys only; no trust-store changes."""

import importlib.util
import ssl
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crypto_support import certificate, private_tls_key, verify_ed25519


@unittest.skipUnless(
    importlib.util.find_spec("cryptography"), "Installer runtime dependency required"
)
class CryptoTests(unittest.TestCase):
    def test_exact_ed25519_signature_and_wrong_algorithm(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        signature = key.sign(b"exact reviewed manifest")
        verify_ed25519(b"exact reviewed manifest", signature, public)
        for payload, proof in (
            (b"changed manifest", signature),
            (b"exact reviewed manifest", b"wrong"),
        ):
            with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
                verify_ed25519(payload, proof, public)
        wrong = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        with self.assertRaisesRegex(ValueError, "E_SIGNATURE"):
            verify_ed25519(b"exact reviewed manifest", signature, wrong)

    def test_real_certificate_and_key_load_without_system_openssl(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        key = private_tls_key()
        cert = certificate("fixture.test", "127.0.0.1", key)
        parsed = x509.load_pem_x509_certificate(cert)
        self.assertFalse(
            parsed.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        )
        names = parsed.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        self.assertEqual(names.get_values_for_type(x509.DNSName), ["fixture.test"])
        public = serialization.load_pem_private_key(key, password=None).public_key()
        self.assertEqual(parsed.public_key().public_numbers(), public.public_numbers())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "key.pem").write_bytes(key)
            (root / "cert.pem").write_bytes(cert)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(root / "cert.pem", root / "key.pem")
            trusted = ssl.create_default_context(cafile=str(root / "cert.pem"))
            self.assertTrue(trusted.check_hostname)
            self.assertEqual(trusted.verify_mode, ssl.CERT_REQUIRED)


if __name__ == "__main__":
    unittest.main()
