# Gateway authority acceptance and rollout runbook

Status: preparation only, 2026-11-06. No deployment, production migration,
restart, provider write, physical action or automatic grant activation is
authorized by this document. See [authority design](gateway-command-authority.md),
[ADR 0036](adr/0036-gateway-command-authority.md) and the
[follow-up evidence](agent-handoffs/2026-11-06-gateway-rollout-results.md).

## Verified starting points and unresolved inventory

The primary checkout was `master` at `fba7cbb`; `c398402` contains authority/V42,
and `69cee10` contains joint household events/V43. HOME-03/ADR 0037/V44 belongs to
Chat A and is separate work. A build from the shared dirty checkout is not a
release candidate. Do not remove V44 from an artifact to pretend it is V43-only.

Read-only observations in this follow-up:

| Location | Observed | Not established |
| --- | --- | --- |
| Windows | Existing `kyrion-postgres` reports successful history through V39; Core 8080 health UP. Queue has 290 succeeded/115 failed rows and no pending/running rows at observation. | Running JAR provenance/pin still needs operator comparison; no new deployment, migration or full host cold start is implied. |
| Pi | Successful V41 history; healthy Core `0eb44f6-deployfix`/Web `0eb44f6`; one node heartbeat aged 3.48 seconds; queue 309 succeeded/130 failed, no pending/running; three binding rows; zero active Calendar leases. Gateway service active since 2026-10-19. Core health 200/UP, devices 401; Windows HTTPS login 200 with normal trust. | Agent destination/config remains protected; current observations do not prove V42 operation, physical acceptance, radio restore or future quiescence. |

The [last Pi activation](status/2026-11-06-pi-update-activation.md) records V41,
Core `0eb44f6-deployfix` and Web `0eb44f6`. Fresh read-only Docker/SQL checks at
2026-11-06 12:58:39 UTC confirm it, including Core image digest
`f7f4038145b69714a15af5b6ed03ae2a8469937d7603a0beab416a9df8604c04`
and Web `77ccb71fa8bf63d390baca20cc707e2697550308c2b20e80117d5b476ea0e281`.
`sudo -n` was unavailable, but existing non-sudo Docker access permitted this
inventory without changing privilege. No protected configuration was exported.
Older provisioning/agent README
documents still describe a Windows Core destination; current destination must be
read and compared, not assumed from either document. Pi hostname recovery is
recorded [separately](status/2026-11-06-local-web-name-recovery.md).

Do not change DNS, firewall, Pi-hole, node credentials or agent destination to
make a probe green. Windows and Pi databases are separate recovery sets, not
interchangeable copies of the same installation.

## Reproducible software acceptance now

From the repository root, with Docker available and JDK 21 selected:

```powershell
& infrastructure/dev/Test-GatewayRollout.ps1 -JavaHome '<existing JDK 21 directory>'
# In a coordinated frozen Core window, for the complete regression/build gate:
& infrastructure/dev/Test-GatewayRollout.ps1 -JavaHome '<existing JDK 21 directory>' -FullCoreSuite
```

The runner accepts no live DB URL, dump, token or device identifier. It holds
`.run/dev-recovery/coordination/core-checks.lock` with `FileShare.None`, forces
fresh Gradle tests and bootJar, and stores source manifests, log and `evidence.json`
under ignored `.run/dev-recovery/gateway-acceptance/<run-id>/`. PASS requires a
zero native exit code, unchanged Core sources, no test failures/errors/skips,
both required Gateway suites and an artifact hash/migration inventory. It never
starts that artifact. Build output may contain V44 or later from A; the report
makes that visible. The isolated migration rehearsal deliberately targets V43.

`GatewayRolloutRehearsalTest` creates only disposable Testcontainers PostgreSQL
databases. It migrates a synthetic source to V41, seeds an old command/binding
and ciphertext markers, performs real `pg_dump`/`pg_restore` into candidate and
rollback databases, applies V42/V43 only to the candidate, and checks retained
data, absent invented provenance/grants and independent V41 recovery. It also
executes the historical claim SQL on the disposable candidate and validates its
history using only V1–V41 resources: database compatibility alone does not restore
the new authority check. No old binary is booted against any live database.

`GatewayAuthorityIntegrationTest` covers missing/unreadable provenance, malformed
legacy payloads, actual member capture, permission withdrawal before release,
disabled/foreign principals, suspended Spaces, revoked/rotated grants, binding
source/action/device/room scope, explicit resave, audit, HOME Voice sessions,
Business Voice denial, synthetic result confirmation, cached replay, retry and
concurrent/duplicate claims. A test's `next` call is never sent to a live gateway.

## Existing tools: permitted purpose and limitations

| Tool | Appropriate use in a later approved window | Important boundary |
| --- | --- | --- |
| `infrastructure/dev/Verify-CoreRuntime.py` | Read-only exact JAR/history checksum and migration/lease gate for Windows. | Refuses both pending and installed-but-absent migrations. A candidate on old DB is expected to fail before an approved migration. Do not bypass the gate to start it. |
| `infrastructure/dev/Start-CoreLan.ps1` / recovery helper | Start the reviewed, pinned artifact after approved migration and inventory. | Not a migration tool; guards/pin must match. Do not run start/restart during this task or overwrite the private pin with build output. |
| `infrastructure/dev/Probe-PiCore.ps1` | Legacy read-only Windows-Core reachability/Voice configuration probe. | Assumes Core port 8080 and Windows-style destination; service-active alone is not fresh heartbeat or authority acceptance. |
| `infrastructure/postgres/backup.ps1`, `verify-restore.ps1` | Protected SQL backup/checksum and restore verification. | Verifier creates a temporary DB **inside the selected existing container**; not completely isolated infrastructure, not original-key/application acceptance. Never supply a production name as a scratch restore target. |
| `infrastructure/nodes/kyrion-node/check-platform-update.ps1` | Read-only Docker/Buildx/source/Compose preflight. | No migration, backup or runtime compatibility proof. |
| `prepare-platform-bundle.ps1`, `install-platform.sh` | Historical fresh-install/initial transfer workflow. | Not an existing-installation updater: bundle exports Windows data/keys and generates target settings/password. Do not rerun for this Pi rollout. |
| `activate-gateway-agent-update.sh` | Explicitly approved agent replacement only. | Copies `/tmp` inputs and unconditionally reloads/restarts the service. Authority wire format is unchanged; do not run it for a Core-only authority update. |
| `backup-zigbee.sh` | Protected copies of existing coordinator/config/database files. | Does not prove a consistent radio restore; copies contain network secrets. No radio request or actual restore is part of this task. |

## Operator release record: required before touching either installation

Record a separate protected record for Windows and Pi: exact source commit,
JAR/image digest and migration catalog; installed version/checksums and success;
configured Core target of **both** Gateway and Voice; fresh heartbeat timestamp
in that exact Core database; node/service state; unresolved pending/running
commands and Calendar leases; original key/document/storage locations; verified
backup hash, restore result, chosen fallback artifact and outage authorization.
Do not print `.env`, tokens, SSH keys, full Compose environment, payloads or event
text into Git or a public report. Query counts/metadata only, using a read-only
transaction. On V39/V41 inspect column existence before referencing V42 columns.

The reviewed V43 release must contain unchanged V1–V41 and exact V42/V43 bytes.
Windows V39 also needs the V40 accounting and V41 identity changes rehearsed;
read [V40 rollout](v40-rollout.md). Pi's actual history must first be confirmed.
If the selected release contains V44 or later, add those migrations, data and
rollback requirements to the approved scope with A; this V43 rehearsal does not
authorize or certify them. Never use `repair`, `clean`, out-of-order migration,
deleted SQL, checksum edits or a pretend target to evade this comparison.

## Later rollout sequence: Windows

1. Obtain a maintenance window and identify the intended database/active Core
   explicitly. Freeze user ingress, all Core writers/schedulers and Gateway/Voice
   event ingress under operator control. A live `commands/next` probe is mutating
   and may release real work: do not use it for inventory. Review pending/running
   work; there is no automatic expiry/cancellation API or safe replay of uncertain
   running work. If disposition cannot be established, stop the rollout.
2. Preserve the exact current pinned JAR, JDK/hash, recovery settings, LAN manifest,
   firewall scope and service launch configuration. Do not repoint the recovery
   helper yet. Back up the quiescent DB, original audit and credential keys,
   bootstrap/recovery state, configuration and matching Knowledge originals.
   Record ownership/ACLs; store secrets separately in protected storage. See
   [backup procedure](postgres-backup-and-restore.md). Personal exports are not a
   complete operational recovery set.
3. Restore into a new isolated PostgreSQL container/network. Preserve original
   data hashes/audit IDs, accounts/roles, nodes, ciphertext, calendars, leases and
   original document/key relationships. No shared Docker/WSL shutdown. Prevent
   any egress to real devices/providers; disable Calendar/HA/Knowledge scheduling
   via reviewed Spring properties in the rehearsal only. Never publish the clone
   on the production Core endpoint or authenticate real nodes against it.
4. Run the approved exact migration catalog there first; check history and data
   again. V42 leaves old authority/grants NULL; V43 adds household tables. Verify
   existing audit history with original keys, allowing new correlated startup
   events rather than requiring an unchanged total audit count. This synthetic
   test suite does not substitute for that protected original-key restore drill.
5. Only after successful rehearsal and a separate apply decision, migrate the
   quiescent real installation through the approved target with a reviewed
   migration-only entry point. The existing start gate is not that entry point.
   No general V42/V43 production applier is supplied by this task: do not improvise
   `bootRun`/disable validation as one. Rehearse the chosen apply command and
   include it in the operator approval record before use.
6. Validate exact JAR/history/checksums and zero unresolved leases; install the
   immutable approved artifact/pin through the existing reviewed launcher, then
   check health, 401 denial and authenticated read-only state. Retain normal TLS/
   LAN restrictions. Keep action ingress paused through binding review below.

## Later rollout sequence: Pi

1. First obtain the required privileged read-only inventory: actual installed
   Compose path (`/etc/kyrion/platform/compose.yml` historically), image digests,
   migration history, node destination/heartbeat and protected storage paths.
   Missing privilege is a blocking gate, not a reason to re-enroll or reset data.
2. Use a Pi-local quiescent recovery set: database custom dump plus checksums,
   installed Compose/environment, TLS/Caddy, original keys, Knowledge storage,
   gateway/Voice enrollment configuration and radio backup files. Preserve existing
   Pi-hole/Avahi/DNS settings. An off-Pi export containing private data/keys needs
   its own destination authorization; the historical attempted export was blocked.
3. Rehearse restore/migration/application checks in a network-isolated container
   with no live mounts or provider/device egress. The original Pi data directory
   and running DB are never a scratch target. Build native ARM64 images with exact
   reviewed tags/digests; image build success is not device acceptance.
4. In the approved apply window, pause scoped ingress/writers, take the final
   recovery set, apply only the reviewed migrations, and activate only the scoped
   Core/Web images. Preserve environment, passwords, original keys, TLS, existing
   DB volume and radio data. No `down -v`, reinstall, broad host reboot or unrelated
   integration restart. No agent replacement is required by the authority change.
5. Verify healthy pinned containers, history/checksums, data/audit preservation,
   HTTPS from Windows without `-k` and fresh heartbeat in the intended Core after
   scoped ingress resume. Do not infer correct routing from `systemctl active` or
   a stale heartbeat in a different database. Follow the binding review before
   allowing button/action traffic.

## Explicit old-button review after migration

Keep Gateway/Voice event ingress paused while the owner reviews each existing
button's gesture, exact device or room and action. `GET /v1/devices/{buttonId}/button-bindings`
returns NULL `grantId` for historical bindings: readable does not mean authorized.
An authenticated eligible human with both `devices:update` and `devices:execute`
must explicitly save the reviewed configuration through the existing UI/PUT
endpoint. Example request shape (identifiers are operator-selected, not copied
from a fixture):

```json
{"bindings":[{"gesture":"single","targetDeviceId":"<reviewed-device-uuid>","action":"turn_on"}]}
```

Use `targetRoomId` instead of `targetDeviceId` for a reviewed room scope; never
both. The server generates fresh grants even on identical saves; a supplied old
`grantId` is not approval. Verify non-null new IDs, actor/Space/button/grant audit
and unchanged reviewed targets using read-only checks. Do not execute a button,
bulk-resave bindings, update grant columns by SQL or attribute old grants to OWNER.
Leave unreviewed bindings disabled. Saving is an authorization change, even
though it does not itself send a lamp command; resume physical input only in an
explicit acceptance window. Partial resave must leave the remaining grants NULL.

## Rollback decision table

| State | Permitted recovery path | Prohibited shortcut |
| --- | --- | --- |
| No live migration applied | Retain original DB/runtime/keys; discard only owned rehearsal artifacts. | Copy a candidate dump or Windows credentials over Pi data. |
| V42 committed, V43 failed | Remain in maintenance; retain failure evidence and backup. Review a roll-forward fix or restore the complete pre-upgrade set into a separate DB/storage target. | Assume the DB is still V41, repair history, launch an unreviewed binary, or delete V42 columns. |
| V42/V43 complete, app problem | Prefer a separately reviewed authority-aware V43-compatible artifact, with matching migration bytes and startup gate. `fba7cbb` is the source baseline containing both V42/V43 and the authority checks, not an automatically deployable signed artifact. | Old Pi V41 image or Windows V39 pin against the migrated DB. `c398402` alone precedes A's V43 commit; its migration inventory is not a V43 fallback. |
| Full pre-upgrade restoration required | Keep writers/events stopped; preserve post-upgrade DB/documents for reconciliation, restore pre-upgrade DB plus matching keys/documents/config into a separate target, validate original history and audit, deliberately switch only after approval. | In-place downgrade, overwrite of the failed target, replay of running commands, or restoring just SQL and regenerating keys. |
| Any post-backup writes or V44+ | Reconcile their data and external effects explicitly; use an artifact compatible with the actual schema. | Claim lossless rollback or V43-only acceptance for later calendar migrations. |

An old Core can structurally read the additive tables and still release commands
without the new checks; Flyway future-version tolerance is not security approval.
Even a complete old-DB restoration reinstates the old authority gap and potentially
pending commands. Keep old-runtime recovery isolated from Gateway/action ingress;
operational return with the new guarantees requires an authority-aware compatible
runtime (or an explicitly reviewed security downgrade, outside this runbook).
Database restoration cannot undo already executed device/provider effects or
restore consumed recovery material safely without deliberate credential/proof
review. A V42+ backup can also resurrect a subsequently revoked grant, role or
session: restored non-null grant IDs are not new consent. Keep all user/action
ingress paused, reconcile post-backup revocations from the preserved failed
target, and explicitly replace reviewed bindings (or clear them through Core)
before resuming. Keep both sealed audit histories intact; do not splice or rewrite
their rows to hide the restore boundary. Never automatically reauthorize bindings
or requeue uncertain commands.

## Still-open real acceptance and release decision

Before GO: protected full original-key/document restore drill on each installation;
fresh Pi inventory and protected agent destination confirmation; exact reviewed migration-only
apply mechanism and artifact catalog; pending/running work disposition; human
binding review; Windows and Pi startup-pin/HTTPS checks. Runtime is not certified
as updated merely because the software suite passes.

Only in a separately authorized on-site hardware slot: single/double/long button
gestures, exact device/room selection, multi-provider/partial/offline outcomes and
correlated actor/Space/grant/command results; two HOME Voice interactions and a new
session after expiry; gateway restart/network interruption/reconnect and late or
duplicate results; OA20 reconnect/power-cycle telemetry honesty; Zigbee/radio backup
restore on a disposable fixture. Confirm visible/audible physical outcomes, not
just API success. Do not test safety-critical devices, Thread/Matter restore or a
host reboot by surprise. These checks remain OPEN; no hardware action occurred
in this preparation task.
