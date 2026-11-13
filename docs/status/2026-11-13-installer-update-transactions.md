# Installer update transaction implementation

The overall installer assignment remains open. This records an implementation
milestone, not product acceptance or a request for user testing. ADR 0061 defines
the update authority, activation boundary and recovery constraints.

## Implemented

`--updates apply`, `resume` and `recover` use the existing authenticated staged
release, host-administrator checks and installation journal. They fence ordinary
startup, stop application writers, capture and verify an encrypted portable
backup, retain a connection-disabled PostgreSQL template snapshot, and preserve
source runtime/configuration. Target Core starts with actual Flyway migrations
under maintenance mode. Activation requires the expected schema, health, denied
application probe, preserved host/account/Space/link identities and Core audit
transition. An interrupted activation retries service start only.

Recovery clones the reserved original database without executing archived SQL or
attempting schema downgrade. It retains the failed database with connections
disabled, including after interruption immediately following its rename. It
restores retained source code/configuration and verified knowledge/recovery files,
keeping newer bytes privately before replacement. Core revokes stale sessions,
device credentials and pending commands after a data rewind. Recovery following
activation requires explicit data-loss acknowledgment and a new encrypted backup
before restoring earlier data. Completed recovery does not repeat revocations.

Native source and target service hosts must implement startup-fence protocol 1;
older unpublished development hosts fail before changes. Compose uses pinned
image identities, untagged archive loading and owned stopped retention containers
to avoid modifying shared Docker tags. PostgreSQL runtime version changes are
refused. Only same-host updates are implemented by this transaction.

## Evidence and limits

Real Core, PostgreSQL 17 and GPG process integration passed on Windows and in the
existing no-egress Linux network namespace. Both an actual synthetic Flyway V50
migration and a deliberately failing nontransactional V50 migration were tested.
Evidence includes payload-switch and activation interruptions, database-rename
interruption, wrong-password rejection before database replacement, offline owner
login after recovery, preserved identities, revoked device authority and retained
failed data. Tests execute no household actions. Runtime PE fixtures are not
executed. Service lifecycle and Windows ACL boundaries are explicitly injected;
these results are not SCM, Docker, reboot or release acceptance.

Reports: `build/update-transaction-windows-report.json` and
`build/isolated-linux/update-transaction-report.json`. Both identify the tested
Core JAR SHA-256. The Linux CI workflow now contains the same namespace test but
has not been dispatched. Core compilation and seven existing targeted security
tests passed. Installer suite: 262 tests, one Windows skip before the subsequent
three additional real-file recovery tests (which passed separately).

## Automatic update continuation (subsequent implementation)

ADR 0062 and `update_automatic.py` now implement optional UTC weekly start-window
and maximum-download consent, bound to the signed-channel revision. The current
frozen worker is required. A generated key is held outside Core-readable secrets
in an administrator-only directory and exported exclusively outside the install
root before enabling. It is never printed, journaled or included in the portable
backup. Interrupted schedule registration can reuse the identical protected key
and matching export. Disabling automatic installation preserves existing keys.

The existing Windows SYSTEM task / Linux root timer becomes hourly with a finite
two-hour invocation. Notification-only scheduling remains the default. A matching
approved automatic transaction may continue offline after startup outside its
start window; manual transactions and data-loss recovery cannot run unattended.
Changed channel/trust revisions revoke unattended approval. The final transaction
journal is retained before the next update. Automatic failures persist only safe
codes and phase, with no child output. DE/EN terminal configuration and status are
implemented; local Web administration is still open.

The real Core/PG17/GPG process integration was repeated on both Windows and Linux
with automatic approval and interrupted activation, including continuation outside
the window. Both passed. Separate window, policy-race, download-limit, manual-flow
refusal and real journal tests passed. Linux tests exercised actual root-only key
and directory modes, export and interrupted registration; Windows key ACL/SCM
execution acceptance remains open. Actual Windows COM validates the hourly
definition without registration. `systemd-analyze verify` validates both daily
and hourly definitions without installing them. Full suites: 276 Windows tests
(two skips), 277 isolated Linux tests (16 skips), plus two new real image-archive
rewrite tests on each. Docker execution in those two tests is injected, not
container acceptance. Ruff passes.

The existing full application restore integration also passed again on Windows
and isolated Linux with the current Core JAR, including interrupted import,
source retirement, audit-tamper refusal, transaction rollback on failed audit
append, offline process restart and credential/command disposition. The hosted
Windows service acceptance runner now additionally prepares a real SCM/ACL/GPG
update and snapshot recovery using a synthetic signed release label over unchanged
public binaries. It does not claim a new application migration. That hosted test
has not been dispatched; no local services/tasks were installed for it.

Native `0.0.0-dev.20261113.7` packages built on their actual OS, executed embedded
probe/version/capability checks, and have no source-map drift:

| Artifact in `build/native-installer/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `kyrion-installer-0.0.0-dev.20261113.7-windows-amd64.exe` | 12490634 | `df394d6c26b215357be171e4cbd64bb9f1e7b5dd45c544231908724a37c96274` |
| `kyrion-installer-0.0.0-dev.20261113.7-linux-amd64.tar.gz` | 14295926 | `26ba85f1333519c907b84cfadbe493ba2ca4186602bbf3753f8f42db773e8332` |

These are unsigned, unpublished development installers; they do not establish
OS installation, cold-boot or ARM64 acceptance. Existing full runtime bundles
predate the new Core/update fence and must be rebuilt before native acceptance.

## Continue independently

The subsequent ADR 0063 implementation closes embedded release-channel bootstrap:
stable native builds require a validated public channel/trust document and bind
its exact bytes to build identity; both builders execute an embedded channel
probe. Setup, continuation and successful restore offer notification-only
scheduling without overwriting existing policies or presenting failed
registration as success. The release workflow accepts the public channel through
`KYRION_INSTALLER_CHANNEL_JSON`. No productive trust or feed is fabricated.

Actual configured-channel native builds passed on Windows and Debian 13/Linux
amd64 using isolated public test keys, with no private key persisted and no feed
connection. Test version: `0.0.0-test.channel.20261113.1`; channel binding SHA-256
`17649cbd4b5d0f99e13e93373354e5d44395f924c2f7df7380a62e16102f1bd4`.
Latest installer suites: 289 Windows tests (three skips), 291 isolated Linux tests
(16 skips), Ruff passed. The native staging unit fixture now injects disk capacity
for synthetic archives and separately tests the unchanged production low-space
refusal; it is not storage acceptance. Setup-continuation tests explicitly inject
the new optional scheduling boundary.

Expanded Core security verification initially found eight missing mandatory
rehearsal-artifact inputs and two stale migration expectations. The suite now runs
with the actual immutable built JAR and correct test driver. Fresh canonical
migration expects schema 49; the historical identity V46 test explicitly targets
46 and retains its data/checksum comparisons. No production migration was changed.
Result: 194 security tests, zero failures/errors, one existing skip. Docker became
reachable in the normal developer execution context, so actual Compose transaction
acceptance should now be pursued using a new scoped synthetic project. Earlier
sandbox access failure is not an enduring absence of the runtime.

Subsequent hardening binds Compose resume/recovery to the same root-owned Unix
socket paths and Docker daemon ID, and refuses updates before quiescence when
account/Space bootstrap is unfinished. Four injected-Docker/real-archive tests
and the journal preflight test pass. Linux restored recovery host keys now retain
the UID/directory access expected by the existing host tool, including replay.
Actual root file-owner tests pass; Windows retains its separate protected ACL.

An added real Unix PTY test exposed a deeper restore issue: recovery host hashes
also bind the *Core database installation identity*, which is not necessarily the
installer's source-host UUID. Core now verifies the original protected key against
the locked restored Core identity, rebinds its host hash transactionally to the
new identity, and still invalidates old codes/sessions. Configured missing or
wrong host keys block activation. Runtime capability checks require this feature;
the Linux helper mounts the restored key directory read-only. The extended actual
Core/PG/GPG restore now passes in the isolated Linux namespace: real interactive
provision, backup, interrupted restore, wrong-host-hash refusal with unchanged
identity, and real interactive code rotation on the target. Passwords/codes and
child console output remain in memory and are never written to reports.

New tested Core JAR SHA-256:
`b117623a942a9c8aa95f5b6dc95ec343896ef273a3cb14882c8db18ff196693a`.
Core compiles and seven targeted security tests pass. Latest Windows installer
suite: 281 tests, three skips. Linux suite before the final capability extension:
283 tests, 16 skips; the extended real Linux restore subsequently passed.
The separately assembled `.10` full Windows runtime bundle predates this Core
fix and is superseded; rebuild compatible installers, service host and full
runtime together before native acceptance. No intermediate development artifact
is a published or accepted release.

Complete actual OS lifecycle/container acceptance and distributed update barriers.
The full requirements matrix remains authoritative for all other open installer
work. The `.7` installers contain the transaction, but full runtime bundles still
need the compatible new Core and service host. Productive release
keys and publication remain external prerequisites; they do not block source
implementation or tests with isolated keys. Do not present this milestone as a
complete installer or ask for partial user acceptance.

## Continued Compose import and recovery hardening

ADR 0064 shares authenticated untagged Docker/OCI loading between fresh setup
and updates. Actual Docker 29.8 testing exposed that engine IDs can be OCI index
digests rather than the configuration witness. A bounded digest-verified graph
now binds both to the reviewed native configuration. Archive-level naming
metadata is removed without altering layers, licensing or content-addressed
blobs. A local two-image fixture confirms that importing an old archive preserves
an independently moved tag and that an actual, never-started container's source
ID resolves for recovery. No scratch-image process executes. Evidence:
`build/docker-image-import-report.json`, generated by
`tests/integration/verify-docker-image-import.py` (not OS boot acceptance).

Old tagged Compose source configurations receive exact immutable pins from their
owned containers. Their original bytes remain retained evidence. Known source
aliases are journaled before replacement so interruption before/after atomic
configuration replacement resumes safely. Recovery selects those source pins;
repair reconstructs only the matching pinned template and selected pin metadata
follows configuration reconciliation. Unknown edits remain refused.

An actual full Compose fixture is under development using the immutable built
Core JAR above, a synthetic V50 and a clean build of tracked public Web sources.
Its first attempt correctly refused existing developer Kyrion containers; none
were modified. The scoped retry explicitly substitutes global discovery,
loopback eligibility and absent systemd prerequisite probes. All project
operations, TLS, database, encryption and migration paths remain real. A passing
report is still required before this can count as full Compose evidence.

The actual fixture now completes fresh and repeated setup, genuine Core/Web TLS
readiness and synthetic local-owner/BUSINESS-Space authentication. It exposed
top-level vendor attestations without descriptor platforms and a real proxy
readiness race: running containers do not guarantee an HTTPS listener yet.
Digest-bound non-executable attestation classification and finite real HTTPS
retries address these. Certificate failures remain immediate errors; validation
is never disabled. Five readiness regressions and the full Windows suite pass:
304 tests, three platform skips. The isolated Linux suite passed 300 tests
(16 skips) before these final six cases; its latest full repeat is pending.
The earlier concurrent-build run exceeded its limit; the successful repeat took
370.554 seconds and was not confused with the timeout. Full update/recovery
container evidence remains pending while the test release contract is corrected.

The corrected full Compose fixture **passes**, including an intentionally legacy
tagged source configuration: actual fresh/repeated setup, Core/Web TLS, local
owner/BUSINESS Space, signed release validation, quiescent encrypted backup,
PG template snapshot, real synthetic Flyway 49→50, interrupted activation,
continuation, post-activation backup and acknowledged recovery to schema 49.
Original knowledge, stable identity/login and immutable source pins are checked.
All pre-existing developer containers remain present. Result:
`build/compose-fixture-55a4e1d233e9410b9ba716ebd602af58/runs/7d469263e6d2413fa22b030a76f698c1/report.json`.
Worker/container source snapshots are retained with that scoped fixture. The
Core JAR is the `b117...` build above. The report explicitly records substituted
loopback eligibility, systemd prerequisite observations and global foreign
installation discovery. It does not establish systemd/SCM/boot or browser SSO
acceptance. No TLS verification was weakened.

Latest full suites: **304 Windows tests (three skips)** and **306 isolated Linux
tests (16 skips, 294.234 seconds)**, Ruff passed. A separate actual Docker
retention replay creates a labeled Caddy container twice through the real adapter,
never executes its image, produces no anonymous volumes and removes only its own
container. `build/docker-image-retention-before.json` is a passing observation,
not a reproduced bug. Manual-only hosted Compose CI is prepared and YAML-checked;
it has not been dispatched. Developer commands and isolation boundaries:
[Compose transaction test](../testing/installer-compose-transactions.md).
