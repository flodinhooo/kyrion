# ADR 0022: Fresh installation boundary for Installer v1

- Status: Proposed
- Date: 2026-10-11

## Context

The existing `install-platform.sh` migrates a development database and existing
keys onto a Pi. It requires a dump, uses mutable local image tags and has separate
HTTPS preparation. It is explicitly unsafe as a general update mechanism. A
consumer-oriented first install must start without developer data while preserving
any existing installation. Core/Web/PostgreSQL already support the always-on
authority boundary in ADR 0016.

## Proposed decision

Introduce a separate Installer v1 for fresh Debian 13 ARM64 installations of
PostgreSQL, Core, Web and Caddy, using authenticated versioned release bundles.
Installation is an explicit local administrator operation. A read-only preflight
and repeat checks under an exclusive lock refuse all existing or ambiguous Kyrion
state. No automatic adoption, update, database import, gateway reconfiguration,
radio provisioning or destructive reset is part of fresh install.

Generate protected keys/secrets locally only for the fresh installation; deployed
Core loads keys without silently creating replacements. Publish trusted local
HTTPS and require a bounded one-time bootstrap secret for first-owner setup.
Core retains account/policy/audit authority; runtime applications never receive
Docker/socket/sudo authority. AI remains optional.

Record stage and ownership in a private journal and preserve persistent state
after failures. Backup coverage and restore verification are distinct. Verify
recovery only in isolated destinations with original keys. Existing-installation
update/rollback and actual disaster recovery require separate future contracts.

## Consequences

- The current migration scripts and live Pi installation remain unchanged.
- A supported reference host and release trust channel are required; signing-key
  custody and distribution must be decided before pilot release.
- Core/Web need bounded secret-file/bootstrap changes and security prerequisite
  fixes before fresh installation is pilot-ready.
- Refusing partial existing state favours preservation over automatic recovery.
- A tested isolated restore is a release gate, not evidence about live hardware.
- This is a planning proposal; no installer or new bootstrap policy is implemented.

See the [implementation plan](../installer-v1-plan.md) and
[readiness risks](../status/2026-10-11-installer-readiness.md).
