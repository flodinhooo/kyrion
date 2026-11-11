# Installer v1 implementation status

## Current guided candidate, 2026-11-11

The [guided implementation record](guided-installer.md) supersedes the historical
entrypoint and ARM64-only source scope below. `guided.py` now owns local review,
actual target inventory, strict authenticated image loading, private raw 32-byte
Core keys, local TLS, private LAN binding, bounded Compose startup, separate Core
and HTTPS readiness, exclusive locking and persistent same-release resume.
The old entrypoint's preflight/write-order failure and encoded-key mismatch with
Core have been corrected. The installer invokes existing Core owner/HOME Space,
login, optional RFC8628 linking and real read-only HA probe/import APIs; no parallel
identity, membership or integration store was added.

Linux AMD64/ARM64 are candidate source paths only. Windows has a read-only probe,
not native provisioning. No platform is newly release-accepted. Full Windows,
multi-device, model/voice lifecycle, update, backup/restore/repair, installer package
trust/distribution and clean-host acceptance remain open. See the current record
for tests, support matrix, installation/release instructions and exact limitations.

## Historical first boundary

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
AI/Gateway/Satellite lint, tests and packaging, Website checks and browser tests,
installer Python checks, shell syntax, isolated Ed25519 signature tests and
Compose validation on pull requests, `master`, and manual dispatch.

`.github/workflows/release.yml` builds an explicit `linux/arm64` bundle on
version tags, validates it, and signs it only inside the protected
`release-signing` environment using `KYRION_RELEASE_SIGNING_KEY_PEM` and
`KYRION_RELEASE_PUBLIC_KEY_PEM`. The publish job is intentionally disabled in
the repository (`&& false`); no GitHub Release is created automatically.
Manual dispatch performs only unsigned build validation and cannot reach the
signing job or any release secret.

The signing private key must be an environment secret and must never be stored
in the repository. The public key should be distributed independently with the
installer. A GitHub-hosted run, ARM64 builder result, and release publication
have not been performed from this workspace.
