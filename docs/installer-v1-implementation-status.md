# Installer v1 implementation status

The first fresh-install boundary is implemented under
`infrastructure/installer-v1`. It is deliberately separate from the existing
Pi migration tooling. It performs read-only platform checks, refuses populated
or symlinked targets, validates exact artifact sizes and SHA-256 digests,
generates random file-backed secrets with restrictive permissions, writes a
redacted journal, and produces a runtime-only Compose/Caddy configuration. Core
continues to own bootstrap expiry and the durable V31 initialization marker.

Core now treats deployed credential and audit-integrity keys as load-only by
default. Missing or malformed keys fail startup; direct constructor-based tests
may opt into generation explicitly. Release tooling builds explicit
`linux/arm64` Core/Web images, emits sizes and SHA-256 digests, and signs the
manifest with detached Ed25519 signatures verified against an external public
key.

The implementation is not a pilot release. The checked-in manifest is a
placeholder with no artifacts, so it cannot install accidentally. Release
signing/key custody, real ARM64 image acceptance, certificate provisioning,
backup/restore verification, and a clean Raspberry Pi rehearsal remain open.

No installer was executed on the development machine and no existing database,
secret, migration, gateway or hardware configuration was changed.

## CI and release gate status

`.github/workflows/ci.yml` runs Core tests/boot JAR, Web lint/type/test/build,
installer Python checks, shell syntax, isolated Ed25519 signature tests and
Compose validation on pull requests, `main`, and manual dispatch.

`.github/workflows/release.yml` builds an explicit `linux/arm64` bundle on
version tags, validates it, and signs it only inside the protected
`release-signing` environment using `KYRION_RELEASE_SIGNING_KEY_PEM` and
`KYRION_RELEASE_PUBLIC_KEY_PEM`. The publish job is intentionally disabled in
the repository (`&& false`); no GitHub Release is created automatically.

The signing private key must be an environment secret and must never be stored
in the repository. The public key should be distributed independently with the
installer. A GitHub-hosted run, ARM64 builder result, and release publication
have not been performed from this workspace.
