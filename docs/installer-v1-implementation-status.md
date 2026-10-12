# Installer v1 implementation status

The first fresh-install boundary is implemented under
`infrastructure/installer-v1`. It is deliberately separate from the existing
Pi migration tooling. It performs read-only platform checks, refuses populated
or symlinked targets, validates exact artifact sizes and SHA-256 digests,
generates random file-backed secrets with restrictive permissions, writes a
redacted journal, and produces a runtime-only Compose/Caddy configuration. Core
continues to own bootstrap expiry and the durable V31 initialization marker.

The implementation is not a pilot release. The checked-in manifest is a
placeholder with no artifacts, so it cannot install accidentally. Release
signing/key custody, real ARM64 image acceptance, certificate provisioning,
backup/restore verification, and a clean Raspberry Pi rehearsal remain open.

No installer was executed on the development machine and no existing database,
secret, migration, gateway or hardware configuration was changed.
