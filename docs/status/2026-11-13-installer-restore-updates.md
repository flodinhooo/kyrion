# Installer continuation: operational restore and updates

The overall installer assignment remains open. This report supersedes the
restore work order in the preceding integration report; it is not a request for
user acceptance.

## Implemented restore path

ADR 0057 defines the source-fenced, fresh-target restore protocol. The existing
installer now captures a PostgreSQL 17 binary table snapshot alongside the
encrypted operational backup. It prepares a signed, compatible fresh runtime
without activating it. An explicitly retired source emits an authenticated
receipt bound to the backup digest and the new installation UUID. The target
verifies that receipt before importing data into the schema created by its own
verified Core. Archived SQL, functions and schema definitions are not executed.

Original accounts, memberships, Spaces, encrypted application keys and knowledge
are preserved. Core owns the transactional security disposition: old sessions,
recovery grants and device credentials are invalidated; pending device commands
are failed; integration control and scheduled calendar synchronization require
review. Core verifies the existing audit chain and appends a sealed restore
event in the same transaction. The target receives a new host identity.

Import interruption is resumable while the target remains inactive. Repeating a
completed restore does not replace subsequently written application data.
Managed-key replacement has explicit crash recovery checkpoints.

## Developer evidence

- Windows source suite: 227 tests, one skip.
- Isolated Debian Linux source suite: 227 tests, 16 platform-specific skips.
- Core permit/security unit tests: four tests passed with JDK 21.
- Real PostgreSQL 17 binary snapshot roundtrip on Windows, including every byte
  value, quoted paths, sequence restoration, repeated import and invalid foreign
  keys. This is a native process test, not SCM acceptance.
- Real Core/PostgreSQL/GPG application restore on both Windows and isolated
  Linux: source retirement, inactive preparation, interrupted import, corrupted
  audit rejection, audit-write transaction rollback, offline login after process
  restart, preserved Space/account/link rows and new host identity passed.
  Lifecycle operations use a process adapter, not Docker/SCM. Linux uses a
  private network namespace with no egress. The identity link is a seeded test
  fixture; this does not replace browser SSO acceptance.
- Tested Core JAR SHA-256:
  `2234b42a07a271d474ddfd3c2ea853f1780c9f7d1d0d40f6bed30e7fdeddd056`.
- Ignored local reports: `build/application-restore-windows-report.json`,
  `build/isolated-linux/application-restore-report.json`,
  `build/portable-database-windows-report.json`.
- CI prepares the corresponding PostgreSQL 17 Linux scenario and the native
  Windows service restore scenario. These workflow changes have not been run
  on hosted runners in this development session.

No real household devices, public releases or host services were changed.

## Explicit boundaries and remaining source work

Portable activation currently requires PostgreSQL 17, schema 49, an exactly
matching trusted target schema and a new or matching prepared target. Legacy
dump-only backups can still be verified, but are not activated by this path.
An unavailable or unfenced source cannot authorize activation. Same-root
disaster recovery, arbitrary schema transitions and distributed authority
transfer remain implementation work. Native Windows SCM restore, actual
container UID permissions and cold boot remain target-environment acceptance.

## Installed update checks (ADR 0058)

The native installer now offers `--updates configure|status|disable|rotate-trust`. Explicit
configuration reviews the HTTPS feed, independently supplied public trust store
and executable digest before copying an immutable maintenance worker. A Windows
SYSTEM boot task repeats daily; Linux uses a root oneshot service with a boot
and daily timer. No interactive login or user Python is required. The background
entrypoint runs without prompts. It reuses the real signed release checker and
persists a policy-bound attempt/result. Failures preserve the last verified
result and store only an allowlisted error code. Retirement and uninstall remove
only the owned schedule. Timer publication is atomic and registration resumable.
Installed trust rotation reuses the signed rotation verifier, advances exactly
one epoch and changes the policy revision without changing the OS task. Replay
and a changed reviewed rotation document are rejected.

Actual Windows COM definition validation and actual isolated Linux
`systemd-analyze verify` passed, without registering or starting host jobs. Unit
tests cover real signature selection, network failure, stale policy revisions,
inactive targets, invalid URLs, interrupted publication and configuration resume;
SQL, frozen-worker and scheduler boundaries are injected in these unit tests.
The Windows hosted integration runner additionally prepares real SYSTEM task
execution of its unreleased worker and verifies rejection before network access.
That privileged scenario has not been executed in this session. Local Debian
has no running systemd manager; no Linux job execution or cold boot is claimed.

Configuration currently requires a released embedded version and an explicit
authenticated feed. Development builds cannot pretend that a public release
exists. The `.4` native Windows/Linux test packages contain the update-check milestone's
allowlisted sources, verified against both embedded source hash maps. They
remain unsigned, unpublished development artifacts. Local Web update
notifications, transactional installation, maintenance windows, migrations,
interrupted update recovery and distributed coordination remain source work.
Checking does not install an update. The complete requirements matrix remains
authoritative for all other open work.

Update-check milestone source suites: 238 tests on Windows (one skip) and isolated Debian Linux
(16 platform skips). Ruff passed, DE/EN locale keys match, and both prepared CI
workflow documents parse. No hosted workflow was dispatched.

| Local artifact | Bytes | SHA-256 | Verification |
| --- | ---: | --- | --- |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261113.4-windows-amd64.exe` | 12417292 | `2a1a31964bffb30967e71a77b0fc80bb9abf2b1d7c4ca22017d3dca1d87d7bc7` | Actual frozen version/probe, current source map; no service/cold boot acceptance |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261113.4-linux-amd64.tar.gz` | 14222644 | `6ed5bcc0c7c4cfc1a9869a7b38361e6694342ee6b8cf3c54906d2f86471b5901` | Actual frozen version/probe on isolated Debian; no ARM/old-glibc/boot acceptance |

These ignored build outputs are not public download links or published releases.

The updated local Windows runtime bundle is
`build/windows-native-bundle-dev8/kyrion-windows-amd64.zip`: 247559859 bytes,
SHA-256 `705afe1d15c07b5c273f7c557270ce721f9c59b3eaa9d0870266bc61951272e2`,
6114 public files. Its manifest digest is
`61ad722570fcfa139939849991acea5bea279e86b27fcca9e8611f577ed8cc38`.
The actual frozen `.4` installer accepted its ephemeral development signature
and verified the full payload without activation. The private test signing key
was never persisted. This is not Authenticode or productive release acceptance.

## Authenticated update download continuation (ADR 0059)

`--updates download --target ROOT` now rechecks the configured signed channel,
authenticates the exact manifest digest and reviews artifact sizes before large
transfers. It streams HTTPS artifacts into protected staging with actual byte
progress. Interrupted transfers resume with validated Range responses; ignored
Range responses restart the same owned partial. Invalid headers, redirects,
untrusted TLS certificates and incorrect digests cannot publish a verified file.
The existing native ZIP/PE/file validators and Linux image archive/tag validators
are reused. Runtime services and installed release configuration are unchanged.

Signed index proof and public trust snapshots accompany the staged manifest.
Before a future transaction uses it, revalidation checks signature expiry, current
policy revision, release sequence, platform and compatibility again. A changed
policy or expired proof requires fresh authorization. Manual staging also works
when periodic checks are disabled. No automatic activation or database mutation
is claimed by successful download verification.

Developer tests use real loopback HTTPS servers and certificate validation, real
Ed25519 signatures, journal/files and archive validators. Payloads are synthetic
and are never executed; installed-schema queries and host/scheduler guards are
injected in staging tests. Current source verification and artifacts are recorded
below as they complete. The update backup/migration/activation coordinator,
maintenance windows and distributed update barriers remain open source work.
The `.4` artifacts above predate this download continuation.

Download milestone verification: 248 Windows tests (one skip), 248 isolated Linux
tests (16 skips), Ruff and matching DE/EN locale keys passed. Ten download tests
exercise actual loopback HTTPS, including certificate rejection, interrupted
whole-staging resume and immutable runtime configuration. Synthetic Linux TAR
image identities and native ZIP/PE contents are validated without execution.

Both `.5` native packages passed actual frozen version/probe checks and their
source maps match this download implementation. They remain unsigned and
unpublished, with platform installation acceptance false:

| Local artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261113.5-windows-amd64.exe` | 12430805 | `74362f2182f9fe5e04dd86e43af9b356d143dd15bdf29806289c2e07684ca824` |
| `build/native-installer/kyrion-installer-0.0.0-dev.20261113.5-linux-amd64.tar.gz` | 14235897 | `ef20d5b88cb17f6f9c6d076954117869643833756e96c78684074ba2c6b27811` |

## Core maintenance start continuation (ADR 0060)

Core now supports a host-controlled `KYRION_OPERATIONAL_MAINTENANCE=true` process
start. Only exact GET/HEAD health routes pass its earliest servlet filter;
application requests return 503 `OPERATIONAL_MAINTENANCE`. Global application
scheduling is disabled for this start. Normal mode retains existing scheduling
and authentication. Flyway and startup invariants still run; Core's sealed
`core.started` audit event is deliberately preserved.

Seven Core unit tests passed (three maintenance tests plus the four existing
permit/protected-file tests). The updated actual Core/PostgreSQL/GPG process
integration passed on Windows and isolated Linux. It verifies healthy maintenance
startup, blocked login/Space routes, unchanged accounts/Spaces/sessions and other
audit records, exactly one expected startup audit event, normal access after
restart, then all existing interruption/audit/identity/offline restore checks.
The tested Core JAR digest is
`03f1ab64000868510b4cbf09851b5dba85b8ffba4a9b14a2f6947cc5428c4697`.
Reports use the same ignored report paths listed above. These remain actual
process tests with an injected lifecycle adapter, not SCM/Docker/boot acceptance.

This property is currently available for direct Core process starts; it is not
yet selected by an installed transactional updater. The `.5` installer artifacts
do not contain Core. The earlier `dev8` runtime bundle contains the earlier Core
digest, so it does not provide this maintenance mode. Runtime repackaging must
follow coordinator integration; no packaged support is claimed prematurely.

| Environment | Actual evidence | Remaining acceptance |
| --- | --- | --- |
| Windows 11 x64, build 26300 | Frozen installer probe/version, native PG17/Java21/Core/GPG processes, TLS, restore and maintenance start | Fresh OS prerequisites, SCM/task execution, system reboot; hosted scenario prepared but not run |
| Isolated Debian 13 x64 WSL guest | Frozen installer probe/version; PG17/Java21/Core/GPG process tests, no-egress network namespace, systemd definition parser | No running systemd manager, container UID acceptance, cold boot or old-glibc compatibility |
| Ubuntu 24.04 x64 hosted CI | PostgreSQL17 namespace/process and native packaging scenarios prepared | Workflow not executed in this session |
| Linux ARM64 / suitable Raspberry Pi | Architecture paths and release selection source | No actual native artifact, hardware or boot acceptance in this session |

No row constitutes a production support release. Transactional update execution,
consistent pre-update quiescence, protected automatic-backup key custody,
post-migration activation, interrupted-update recovery and distributed barriers
remain source work, independently of unavailable host acceptance environments.

## Backup/update integration correction

Linux operational capture now selects only the existing allowed backup members,
matching the native backend. Public installed maintenance executables and staged
download proofs remain intact on disk but do not enter operational data archives.
This fixes backups after configuring the new update worker or staging a release.

Linux capture now persists the originally running Core's restart obligation before
stopping it. A timeout after a successful stop still attempts recovery. A failed
restart retains the obligation, and a subsequent backup invocation recovers it
even when Core is currently stopped. Diagnostic export exposes only a recovery
required boolean. Inactive/retired installations are rejected before capture can
restart any service on either backend. Ordinary backup still restarts Core before
encryption; the uninterrupted pre-update quiescence transaction is not implemented
by this correction.

Current full installer suites: 253 Windows tests (one skip), 253 isolated Linux
tests (16 skips), Ruff passed. New archive-selection and interrupted-service tests
use real files/journals with injected Docker/SCM/crypto boundaries; they are not
fresh container/service acceptance. The actual isolated Core/OIDC/Home Assistant
scenario also passed again against the new Core JAR: linked BUSINESS owner,
TLS-verified synthetic identity issuer, selected entity/room import, one deliberate
synthetic action, actual scheduled state refresh observed after 58.1 seconds,
removed-entity handling, disconnect and offline identity after process restart.
Its report is `build/isolated-linux/core-ha-report.json`; no household devices or
outgoing provider connections were used. The `.5` native artifacts predate this
backup correction and the separately built Core maintenance feature.

## Concrete continuation

Continue with the actual update transaction, using the authenticated staged
inputs and Core maintenance start already implemented. Persist and enforce an
update startup fence before quiescence; capture a consistent encrypted backup
without reopening application writes; stage/switch owned runtime payloads;
execute verified migrations under maintenance mode; check actual schema/health;
then cross an explicit activation point. Interrupted phases must resume or offer
validated backup recovery, without promising schema downgrade. Configure protected
automatic-backup key custody and an owner-approved maintenance window before
enabling automatic installation. None of these missing source tasks is blocked
by production signing-key availability. Distributed update barriers and the other
open requirements remain in the full requirements matrix. Do not request user
testing or describe this checkpoint as ready for overall acceptance.
