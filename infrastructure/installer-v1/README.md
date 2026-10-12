# Kyrion Installer v1

This is a fresh-install boundary for Debian 13 ARM64 and 64-bit Raspberry Pi
OS. It installs PostgreSQL, Core, Web and Caddy from a release bundle. It does
not adopt, migrate, update or delete an existing installation.

The release directory must contain a signed, immutable `manifest.json` and the
listed artifacts. The manifest records exact SHA-256 digests and byte sizes;
the detached Ed25519 signature is verified by the release process before the
bundle is copied to the host. The placeholder manifest in this repository is
deliberately not installable.

Run on a fresh target only, as root, after installing Docker Engine, the Docker
Compose v2 plugin, curl, OpenSSL and Python 3:

```sh
KYRION_RELEASE=1.0.0 KYRION_HOSTNAME=kyrion.local ./install.sh
```

The same variables can be supplied from an approved automation environment for
non-interactive operation. `preflight.py` is read-only. `install.sh` refuses
non-empty or symlinked targets, creates 0700 secrets and writes a redacted
private journal. It never prints a secret. The protected bootstrap value is
delivered to the local operator from `bootstrap.secret`; Core enforces its
30-minute expiry and the durable V31 initialization marker.

The runtime template binds only HTTPS, keeps PostgreSQL/Core/Web internal to a
Docker network, drops container capabilities and does not install AI. Local
TLS uses an administrator-provided certificate and key in the protected TLS
directory. Trust that certificate on each phone or browser according to the
chosen local CA policy. No router port forwarding is configured.

This first implementation still needs a release signing operation, real image
archives/digests, a clean Debian ARM64 rehearsal, and isolated backup/restore
acceptance before a Raspberry Pi pilot can be approved. Updates, migration of
existing installations and full disaster recovery remain separate contracts.
