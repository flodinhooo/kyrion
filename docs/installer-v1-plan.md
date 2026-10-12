# Installer v1 implementation plan

Date: 2026-10-11. Status: **planned; no installer v1 has been implemented or deployed**.

Read the [readiness review](status/2026-10-11-installer-readiness.md),
[current TODO](status/TODO.md) and [proposed ADR 0022](adr/0022-fresh-installation-boundary.md).
Existing installation, database, keys and radio services must remain untouched.

## User outcome and scope

An administrator can install a versioned Kyrion control plane on a fresh,
supported Debian 13 ARM64 host, establish trusted local HTTPS, create the first
owner and use Core/Web without AI or the development PC. The Raspberry Pi 5
8 GB is the reference hardware, not a new appliance commitment.

The installed slice is PostgreSQL, Core, Web and Caddy. Installer v1 does not
import a development database, install models, create cloud accounts, provision
radios, change gateway configuration or expose remote control. Device onboarding
uses existing bounded Core flows after setup. The acceptance scenario uses a
mocked adapter in isolation; real device acceptance is recorded separately.

No Windows/macOS installer, mobile application, disk imaging, public marketplace,
automatic update, migration of existing installations, or data replacement is
included. A separate future updater must establish backup, migration compatibility
and rollback; the current migration script must never serve as that updater.

## Security implementation baseline (2026-10-11)

Core/Web now implement the bounded bootstrap and delegation in
[ADR 0023](adr/0023-security-bootstrap-and-delegation.md). See the
[hardening report](status/2026-10-11-security-hardening.md) for actual regression
and migration evidence. This supersedes the original proposed Core bootstrap
below: do not create a second setup endpoint or token store.

Provision `bootstrap.secret` as a protected 43-character base64url CSPRNG value;
configure `KYRION_BOOTSTRAP_SECRET_FILE` in Core, not Web. Runtime Core must only
read it. Expiry is 30 minutes from mtime. Local renewal is allowed only before the
permanent V31 initialization marker is consumed, after repeating existing-state
checks. Never renew or create this file on ordinary existing-install startup.
Web sends the value in a header and keeps it out of URLs, responses and storage.
Mount permissions, parent-directory ownership, Windows ACL behaviour, TLS,
private operator delivery and isolated recovery still need installer acceptance.
Persist and restore `installation_bootstrap_state` with the database. A restored
initialized installation must remain closed even when the setup file is present.
Existing role grants are preserved; calendar delegation requires explicit owner
intent. Keep Google credentials personal to the linking account.

Installer code has not been implemented. File-backed deployment passwords,
load-only credential/audit keys and release verification remain release gates.

## Prerequisite gates

Before calling any release a pilot-ready installer:

1. Preserve and rerun the implemented R1-R4 security regressions when wiring the
   installer. Calendar permissions, durable grants, delegated ownership and atomic
   audited writes are implemented; no destructive schema changes are allowed.
2. Integrate and accept the implemented protected-file bootstrap on the target
   before LAN onboarding (R5). Provision privately, preserve V31 initialization
   state, and never create a setup window on existing-install startup.
3. Support deployment secrets from protected files and load-only credential/audit
   keys. Missing or incorrect keys are fatal; recovery must never generate new keys
   over restored data. Preserve documented local-development behaviour explicitly.
4. Complete artifact verification, portable HTTPS configuration and fresh-install
   tests. An empty-host development rehearsal may precede these gates, but is not
   pilot readiness.

## Proposed file structure

These paths are implementation targets, not existing delivered functionality.

```text
infrastructure/installer-v1/
  README.md                         operator instructions, supported host matrix
  install.sh                        explicit administrator entrypoint
  preflight.py                      read-only host/state/port/resource checks
  bundle.py                         manifest validation, signature/digest verification
  configure.py                      bounded input, atomic files, CSPRNG secrets
  provision.sh                      only fixed approved installation operations
  verify.sh                         bounded readiness and trusted HTTPS checks
  backup.sh                         full scoped deployment backup
  verify-restore.sh                 isolated restore, no live restore target
  templates/
    compose.yml                     runtime-only; no source build contexts
    Caddyfile                       validated hostname and explicit LAN binding
    platform.env.example            non-secret defaults; no developer addresses
    install-config.example.json     hostname, LAN IP, locale, release version
  schemas/
    release-manifest.schema.json    versioned artifact/architecture contract
    installation-state.schema.json paths, stages and immutable release identities
    backup-manifest.schema.json     coverage, hashes, separate restore verification
  locales/en.json
  locales/de.json
  tests/
    test_preflight.py               collisions, existing state, symlinks, concurrency
    test_bundle.py                  signature, checksum, path traversal, size limits
    test_configuration.py          parsing, permissions, atomicity, secret redaction
    test_failure_recovery.py        interrupted installs and scoped cleanup
    compose-contract.test.py        exposures, secrets, healthchecks and hardening
    integration/clean-room.sh       disposable Debian ARM64 environment only
    fixtures/                      synthetic inputs; no owner backups or keys
  release/
    build-bundle.ps1                public runtime images only, no DB/key export
    sign-manifest.sh                offline release operation; signer never bundled
services/core/src/main/kotlin/dev/kyrion/core/security/
  FirstOwnerBootstrap.kt            limited bootstrap authority; no host commands
services/core/src/main/kotlin/dev/kyrion/core/config/
  DeploymentSecrets.kt              file-backed secret validation/load-only mode
docs/installer-v1-plan.md
docs/adr/0022-fresh-installation-boundary.md
```

Use POSIX shell for orchestration and Python standard library for structured
validation and file operations; no new third-party installer framework. Require
the supported host's Python 3, OpenSSL, curl, Docker Engine and Compose v2 plugin.
Use the existing test stack for Core and Web bootstrap/RBAC regressions. Schema
files document strict contracts; actual boundary validators must reject unknown
keys, invalid types and oversized input without depending on unchecked casts.

Changes to existing code are bounded: Core deployment secrets/bootstrap and
the identified security fixes; Web setup token entry, bilingual messages and
tests; `.dockerignore` and runtime health dependencies; new runtime Compose
template. Do not rewrite the development migration, existing Pi Compose or Flyway
history in order to ship fresh installation.

## Release bundle and trust

Ship one public, versioned bundle for `linux/arm64`, containing four OCI image
archives, templates, installer files, a bounded manifest and detached signature.
Include no database dump, `.env` containing credentials, key files, personal
recordings or provider tokens. Use immutable image digests and record exact base
image versions, build source revision, PostgreSQL major, artifact bytes/hashes,
minimum installer version and supported host architecture in the manifest.

Use a detached Ed25519 signature over the exact manifest bytes, verified with
OpenSSL and an out-of-band pinned release public key before loading
images or running bundled code. The download entrypoint and verifier themselves
must come from the trusted, versioned release; a key included in an untrusted
bundle is not authority. Verify every declared file, reject undeclared executable
content, absolute paths, `..`, links, duplicate entries and excessive archive sizes.
Cross-check loaded image IDs/platform against the signed manifest. Do not execute
configuration as shell, interpolate arbitrary commands, or download and execute
an unverified script as root. Invalid signature/checksum always stops installation.

Offline installation is supported only after the reviewed prerequisites and
complete signed bundle are available. Explain first-download internet needs and
runtime AI independence separately. Signing-key custody/rotation and the initial
trusted release channel remain release decisions, not completed infrastructure.

## Setup flow

1. **Read-only preflight:** validate OS/architecture, administrator identity,
   prerequisite versions, Docker reachability, disk/RAM using manifest requirements,
   time, target LAN interface/IP/hostname and DNS/mDNS resolution. Do not install
   Docker implicitly or change firewall/router configuration.
2. **Detect existing state:** check all target paths, symlink parents, known
   Kyrion services/containers/Compose project, database contents and credential/TLS
   files. Any existing or ambiguous state returns `INSTALL_EXISTING_STATE`; offer
   read-only diagnostics and the separate recovery/update instructions. Do not
   infer freshness from unused ports or an empty PostgreSQL directory alone.
3. **Review:** select German/English, hostname and reachable LAN address. Display
   validated release, exact paths, exposed ports, required privileges and optional
   external data flows. Require explicit administrator approval of this plan before
   host writes. No AI or external provider is enabled by default.
4. **Verify release:** authenticate the manifest and all artifacts, then load images.
   Preflight must already have passed. Hold an exclusive installation lock and
   repeat state checks under the lock to prevent concurrent-install races.
5. **Create protected state:** with `umask 077`, create a private staging directory
   and a versioned installation journal. Generate a random database password,
   separate 32-byte credential/audit keys and a TLS private key locally. Write
   atomically with exclusive creation and explicit ownership. No overwrite or key
   regeneration is permitted. The journal stores paths/stages, never secret values.
6. **Start local control plane:** start PostgreSQL, Core and Web with loopback/private
   endpoints only. Run Flyway only against the newly created database. Readiness
   waits have per-request timeouts and an overall deadline; distinguish unhealthy
   database, failed migration and unhealthy application.
7. **Enable trusted HTTPS:** generate a self-signed leaf certificate (`CA:FALSE`)
   with validated hostname/IP SANs. Export only the public certificate/fingerprint.
   Explain client trust and expiry/renewal in both languages. Verify hostname and
   certificate using `curl --cacert`, never a successful `--insecure` check as
   acceptance. Publish only HTTPS on the approved LAN address.
8. **Claim owner:** accept a short-lived, single-use installer-created bootstrap
   secret through the existing Web/Core setup flow. Deliver it via a protected
   local administrator file, not logs, URL query parameters or browser storage.
   Core validates/consumes it atomically with owner creation; rate-limit attempts,
   expire it and close setup permanently after success. Do not put Docker authority
   into Core or Web. A lost/expired setup secret requires an explicit local admin
   operation, never account reset on a populated database.
9. **Verify and report:** confirm owner login, effective permissions and audit
   integrity on synthetic actions, mark the installation healthy, and generate a
   secret-free versioned report with correlation ID and recovery instructions.
   Optional integration/AI onboarding happens afterwards in Core-owned flows.

## Filesystem and container policy

Final paths follow existing operating conventions but are independent of the old
migration bundle:

| Path                            | Contents and access                                                     |
|---------------------------------|-------------------------------------------------------------------------|
| `/etc/kyrion/platform/`         | Root-owned configuration; private directory, non-secret env and Compose |
| `/etc/kyrion/platform/tls/`     | Private key 0600, public leaf certificate 0644; no overwrite            |
| `/var/lib/kyrion/postgres/`     | New database data, PostgreSQL image's validated numeric owner           |
| `/var/lib/kyrion/secrets/`      | Credential/audit keys 0600; Core UID 10001; read-only runtime mount     |
| `/etc/kyrion/platform/secrets/` | DB password/bootstrap secret with explicit per-service readers          |
| `/var/lib/kyrion/caddy/`        | Explicit proxy state, access limited to its runtime identity            |
| `/var/lib/kyrion/installer/`    | Root-only state journal, install lock and redacted diagnostics          |
| `/var/backups/kyrion/platform/` | Protected scoped backups; owner-selected protected off-host destination |

Read-only root filesystems, `no-new-privileges`, dropped capabilities, bounded
tmpfs, explicit CPU/memory limits and immutable images apply. Core/Web remain
non-root. PostgreSQL is never published; Core 18080 and Web 3000 stay loopback-only.
Caddy has only the binding capability if needed. No runtime gets Docker socket,
sudo or general host execution. Verify both IPv4 and IPv6 exposure; DNS is not
authorisation. Existing gateway/radio configuration is outside installer authority.

Use file-backed PostgreSQL password support and Core's proposed validated secret
file/config-tree reader rather than copying passwords into ordinary env values.
Verify mount UID/mode on the actual supported Compose implementation; do not rely
on secret metadata that a local bind mount does not enforce. The Web image receives
no provider credentials or Core keys. File-based optional provider configuration
requires explicit enablement; no shared consumer OAuth secret is shipped (ADR 0021
is proposed, not implemented). Missing key after restore is a blocking error.

## Failure and interruption handling

Every result has `formatVersion`, installation/correlation ID, stage, stable code
and retry guidance. Human messages come from German/English resources. Return
distinct nonzero exit codes for validation, refusal, dependency and health failures;
do not expose raw provider responses, env expansions or unrestricted service logs.

| Code                                               | Required behaviour                                                          |
|----------------------------------------------------|-----------------------------------------------------------------------------|
| `INSTALL_UNSUPPORTED_HOST`                         | No platform writes; explain supported OS/architecture                       |
| `INSTALL_EXISTING_STATE`                           | No replacement, stop/start, migration, key generation or automatic adoption |
| `INSTALL_LOCKED`                                   | Refuse second installer; no stale-lock takeover without local review        |
| `INSTALL_PREREQUISITE_MISSING`                     | Identify tool/version; no implicit package-manager changes                  |
| `INSTALL_PORT_CONFLICT`                            | List bounded listener metadata; never kill another service                  |
| `INSTALL_CAPACITY_INSUFFICIENT`                    | No provisioning; include required/observed resources                        |
| `INSTALL_BUNDLE_INVALID`                           | Stop before image load/platform writes; no verification bypass              |
| `INSTALL_SECRET_INVALID`                           | Stop; never log, truncate, replace or regenerate existing key               |
| `INSTALL_DATABASE_NOT_READY`                       | Keep root-only state; bounded retry, preserve database                      |
| `INSTALL_MIGRATION_FAILED`                         | Preserve database and diagnostics; no automatic restore/delete              |
| `INSTALL_CORE_NOT_READY` / `INSTALL_WEB_NOT_READY` | No setup completion; bounded diagnostics                                    |
| `INSTALL_TLS_INVALID`                              | Keep LAN setup unavailable; preserve key/cert for inspection                |
| `INSTALL_SETUP_EXPIRED`                            | Local admin reissue only on an unclaimed fresh installation                 |
| `INSTALL_INTERRUPTED`                              | Record stage; no broad cleanup or silent restart of installation            |

Interrupt/TERM handlers stop only processes created by this install when ownership
is proven. They never use `docker compose down -v`, prune, delete a populated DB,
rotate keys or restore over live data. Resume is an explicit command against the
same journal and verified release; verify all artifacts, path identities and
secret hashes before advancing. If state ownership is ambiguous, refuse. Once an
owner exists, fresh-install resume cannot provision or reset it. Cleanup is limited
to this operation's private temporary files; persistent failure state remains
available for a separately reviewed recovery procedure.

## Backup and restore boundary

Personal encrypted exports are not full installation backups. A scoped platform
backup must record PostgreSQL dump, original credential/audit keys, configuration,
image/release IDs, schema version, TLS material and coverage of optional services.
Keep keys separately protected from an unencrypted dump; require an administrator-
provided protected/encrypted off-host destination for a complete recovery set.
Do not invent new cryptography or store passphrases beside backups. Backup logs and
public manifests expose no secret content. Protect TLS and provider configuration
as secrets, not public configuration exports.

Capture from one explicit installation; quiesce relevant writers when recording
the recovery set. Store checksums, `created`, `integrityVerified`, `restoreVerified`
and `coverage` separately. Missing gateway/Zigbee/Thread/HA backups are `unsupported`
or `partial`, never complete. Define counts/ownership/authentication/audit checks
for the fresh restore, rather than merely counting SQL tables.

Verify in a disposable isolated host/container with new paths and no live mounts,
published LAN ports, provider traffic or production credentials in reports. Restore
the dump and original keys, start the matching Core/Web version with adapters
disabled, verify login/role state, calendar records and audit integrity. Test wrong
and missing keys, corrupted dump and incompatible PostgreSQL major. Never switch
the active database as part of verification. Actual disaster restore and updates
of existing installations remain separately authorised future work.

## Implementation slices and exit criteria

| Order | Slice                                                 | Reviewable result                                                                           |
|-------|-------------------------------------------------------|---------------------------------------------------------------------------------------------|
| 1     | Security prerequisite fixes                           | R1-R5 regression tests green; no destructive migrations                                     |
| 2     | Release and preflight                                 | Signed synthetic bundle accepted; existing-state/corrupt bundle cases refuse without writes |
| 3     | Secrets and runtime config                            | Portable templates, file-backed secrets, load-only keys, valid health dependencies          |
| 4     | Fresh provisioning and setup                          | Disposable host reaches trusted HTTPS and owner login, AI unavailable                       |
| 5     | Failure journal and recovery                          | Every injected stage failure preserves unrelated state and supports explicit safe retry     |
| 6     | Backup/isolated restore                               | Original keys, RBAC, calendar and audit survive a tested recovery set                       |
| 7     | Bilingual documentation and reference-host acceptance | Independent operator follows instructions; evidence and limitations recorded                |

Each slice updates TODO/status and relevant docs. Accept ADR 0022 before implementing
the new installation boundary; record later trust/update choices separately if they
change this proposal. No speculative general plugin/update framework is required.

## Test and acceptance matrix

- Unit: strict configuration, literal input validation (including quotes/newlines),
  mode/UID, missing keys, path traversal, symlinks, interrupted atomic writes,
  redaction and stable bilingual error mapping.
- Contract: all images contain required health tools; readiness validates bodies;
  Compose has no `build`, host DB exposure, Docker socket or privileged runtime;
  keys are read-only and the approved IP is the only LAN listener.
- Integration: clean supported ARM64 Debian host, fresh Flyway, two concurrent
  installers, restart, AI offline, disk full, image mismatch, unhealthy services,
  certificate mismatch and expired bootstrap. Verify refusal also against an
  existing stopped installation, incomplete installation and symlinked target.
- Security: owner creation cannot be stolen/replayed remotely; unprivileged member
  cannot create/edit/delete calendar entries without permission; registration
  does not restore revoked role grants; delegated admins operate only in their
  workspace; RBAC changes are atomic and auditable; blocked requests do not leak data.
- Recovery: dump alone is insufficient; valid protected complete set restores;
  wrong/missing keys fail visibly; check authoritative data and HMAC integrity.
- Preservation: capture hashes/modes and container/service state of sentinel
  fixtures before every refusal/failure case and compare afterwards. No tests use
  the user's actual Pi, database, key store or existing backup destination.
- Operator acceptance: a second person installs from the instructions without a
  development checkout; German/English setup and errors are understandable;
  report distinguishes automated, reference-host and physical-device evidence.

Installer v1 is accepted only when this matrix has recorded results, the required
security fixes are closed, fresh install and isolated restore pass, existing-state
refusal changes no user data, and no essential non-AI path depends on a developer PC.
Hardware-specific claims require a separate owner-approved real-device exercise.
