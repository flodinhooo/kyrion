"""Audited library primitives used by frozen installers, never custom crypto."""

from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone


def verify_ed25519(payload: bytes, signature: bytes, public_pem: bytes) -> None:
    from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        key = serialization.load_pem_public_key(public_pem)
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("E_SIGNATURE")
        key.verify(signature, payload)
    except (TypeError, ValueError, InvalidSignature, UnsupportedAlgorithm) as error:
        raise ValueError("E_SIGNATURE: release authentication failed") from error


def private_tls_key() -> bytes:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def certificate(hostname: str, address: str, private_pem: bytes) -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("E_TLS_KEY")
    subject = x509.Name(
        [
            x509.NameAttribute(
                NameOID.COMMON_NAME,
                hostname if len(hostname) <= 64 else "Kyrion local installation",
            )
        ]
    )
    now = datetime.now(timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(hostname), x509.IPAddress(ipaddress.ip_address(address))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(key, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
    )
