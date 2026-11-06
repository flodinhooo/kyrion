# Schema-only V45 upgrade and recovery

## Identity integration supplement

Master now also contains optional Identity V46. Earlier V45 artifact hashes and
evidence remain specific to those artifacts. The tool retains target45 as default
and supports explicit `--target-version 46` with an exact V1–V46 catalog. A plan
binds the target version and must be recreated and reviewed for a changed artifact,
tool or target. All maintenance-fence, original-key, backup/restore, provenance
and hardware gates below remain required. No live rollout is authorized or
performed by source integration. Divergent feature-only Identity V44 needs its
own reviewed compatibility plan; validation is not bypassed.

Combined evidence: [Identity master integration](agent-handoffs/2026-11-06-identity-master-integration.md).

Status: implementation and synthetic rehearsal, not permission to apply to an
installation. This supplements, without replacing, the original-data/key and
hardware gates in [Gateway rollout](gateway-authority-rollout.md). The earlier
V43-only rehearsal does not establish V45 acceptance. Decision:
[ADR 0040](adr/0040-artifact-bound-schema-migration.md). Calendar consent semantics:
[ADR 0037](adr/0037-voluntary-personal-calendar-disclosure.md) and
[ADR 0038](adr/0038-selected-household-calendar-delivery.md).

## Operator tool and prerequisites

`infrastructure/dev/Migrate-CoreSchema.py` uses Python's standard library, JDK 21
(`java` and `javac`), and **only the selected Core JAR's** Flyway, PostgreSQL JDBC,
Jackson and commons-logging libraries. Nothing is downloaded. Application classes,
Spring libraries, configuration and callbacks are not extracted or loaded. SQL
comes only from that same byte-for-byte SHA-256 checked artifact. The supported
catalog is exactly V1–V45; later catalogs require a reviewed tool/test change.
No Core boot, HTTP server, scheduler, queue poller, provider or device client runs.
It supports successful, contiguous starting histories V39/V41/V43/V44/V45 only.
The final V45 case supports independent restored-data validation/no-op, not a
downgrade. Flyway validates real stored checksums; there is no history emulation.

The migration role needs existing schema DDL/data permissions, catalog visibility,
`pg_stat_activity` visibility and access to `pg_control_system()` for cluster
identity. Missing access fails closed. Arrange minimal operator credentials through
the installation's protected procedure; do not alter roles or authentication to
make a rehearsal pass. This task changes neither privileges nor database settings.

Keep a protected JSON connection file outside Git, with owner-only Windows ACLs
or POSIX mode 0600. Populate it through an approved secret-handling path, never
through a command containing a password or a transcript-visible shell expansion.
It contains `host`, integer `port`, `database`, `user`, `password`, optionally
`sslmode` (default `verify-full`) and `sslrootcert` (CA file path). Plaintext is
accepted **only when explicitly selected** as `disable` for literal `127.0.0.1`;
use that exception only for an isolated test container or an approved existing
loopback-only DB transport. Remote TLS must use normal certificate/hostname
verification. No password/JDBC URL is accepted on the command line. The child
receives credentials on stdin; third-party diagnostics are discarded, and failures
are reported as machine codes without exception text, SQL or row values.

The plan records artifact/tool/library/migration hashes, successful version and
checksums, a target-identity hash and per-public-table row counts/SHA-256 digests.
It also fingerprints sequence state. Validation permits the planned pending
migrations but replaces Flyway's default future-version tolerance; future or
noncontiguous installed history is rejected.
It contains no credentials or row contents but is still protected operational
metadata. Identity binds cluster system identifier, database OID/name, server
address/port and authenticated role. A clone/restore is a **different target** and
must get its own plan. Table fingerprints include roles, accounts, grants, audit,
ciphertext, queue and calendar states. Changing them invalidates the reviewed plan.
Planning is server-enforced read-only, including Flyway validation connections.
It creates a new local plan file, not schema/history rows. Existing files are not
overwritten. Freeze writers before the final plan: an active heartbeat will stale it.

## Commands (review first; no live apply is authorized here)

Use an immutable reviewed JAR, a SHA-256 from the independently reviewed release
record, the paired tool files, and absolute paths. Do not calculate a hash of an
unknown build and treat that alone as provenance. Windows, from repository root:

```powershell
python infrastructure/dev/Migrate-CoreSchema.py `
  --java-home '<absolute JDK 21 directory>' `
  --artifact '<immutable reviewed Core JAR>' --artifact-sha256 '<approved SHA-256>' `
  --connection-file '<protected target connection JSON>' --plan '<new protected plan JSON>'
```

Linux/Pi uses the same tool and a JDK 21 for ARM64, not just a JRE:

```sh
python3 infrastructure/dev/Migrate-CoreSchema.py \
  --java-home '<absolute ARM64 JDK 21 directory>' \
  --artifact '<immutable reviewed Core JAR>' --artifact-sha256 '<approved SHA-256>' \
  --connection-file '<protected Pi-local connection JSON>' --plan '<new protected plan JSON>'
```

Review the plan against the intended installation/backup/release record. Hash the
**reviewed exact plan bytes** using `Get-FileHash -Algorithm SHA256` or `sha256sum`.
After separate maintenance/apply approval, append the following options to the
same command/paths (PowerShell or Linux syntax as appropriate):

```text
--apply --approve-plan-sha256 <reviewed-plan-SHA256> --expected-target <reviewed-targetIdentity>
```

Apply checks plan hash, artifact hash/catalog, paired tool hash and target/source
state again, rejects other client sessions, and holds a PostgreSQL advisory lock
until done. Every Flyway connection rechecks the target identity before any
migration SQL, including connections opened after the initial check. Plan and
apply do not execute connection-file contents as code. Only
Flyway `migrate` performs schema writes; no repair/clean/baseline/out-of-order or
user-selected target exists. Capture its sanitized JSON result in protected
evidence. A V45 no-op does not consume a calendar lease or start pending commands.

The session check and advisory lock are **not a writer fence**. They coordinate
this tool, not a non-cooperating Core, administrator or provider. The operator must
stop scoped writers/ingress and prevent reconnection for the entire final
backup/plan/apply/postcheck window. A database-wide data scan can be expensive;
use the maintenance window and adequate protected temporary disk. Any drift or
connection error requires investigation and a fresh review, not relaxing checks.
PostgreSQL DDL can commit per migration: failure after V42/V44 is not an automatic
rollback of all versions. Retain result/history and the original backup.

## Separate Windows and Pi execution records

1. Re-inventory each installation read-only. Windows V39 and Pi V41 are previous
   observations, not guaranteed current versions. Compare exact history, runtime
   pin/image, migration checksums, node and Voice destinations and fresh heartbeat
   in the intended Core. Protected agent configuration inspection remains open.
   Resolve pending/running work and existing local/household calendar leases through
   a reviewed disposition; do not poll a live command endpoint to discover work.
2. Choose one approved source/catalog through V45. Include V40 accounting, V41
   identity, V42 provenance, V43 household data, V44 default-private disclosures and
   V45 explicit delivery consent. Do not strip SQL, renumber, repair or edit history.
   Review Chat A's calendar acceptance and subsequent source changes independently.
3. In a later approved window, freeze users, Core/schedulers and Gateway/Voice
   ingress without broad host shutdown. Preserve separate quiescent recovery sets:
   custom-format PostgreSQL dump/hash, exact old artifact/image and JDK/start pin,
   original audit/credential keys, recovery/bootstrap secrets, Knowledge originals,
   protected configuration/ACLs and service launch settings. Pi additionally keeps
   installed Compose/env, TLS/DNS/Caddy and radio/agent/Voice state. No off-Pi private
   export is authorized by this preparation. Never replace Pi data with Windows data.
4. Restore a copy into a new isolated container/storage target with blocked real
   provider/device egress and no live ingress/mounts. Use this tool to plan, review,
   apply and verify V45 there. Validate original-key audit/decryption and document
   recovery through separately controlled checks. A synthetic ciphertext marker
   proves byte retention only. Real original-key/data restore remains OPEN.
5. Only after that protected drill and explicit operational approval, take the
   final recovery set, produce/review a **new plan bound to the quiet real target**,
   and apply with its recorded hashes/identity. A clone's approved plan cannot be
   reused on the original. Store sanitized apply results and a new independent
   read-only V45 plan. Verify unchanged historical audit, accounts/roles/ciphertext,
   retained legacy NULL provenance/grants and no invented disclosures/destinations.
6. Windows: use existing `Verify-CoreRuntime.py` and the immutable matching startup
   pin before a separately approved scoped launch. Pi: use reviewed native ARM64
   images/manifest and preserve the installed Compose, original storage, env and
   TLS; no `down -v`, fresh-install bundle or unrelated restart. A Windows-produced
   rehearsal JAR is not a reviewed Pi image. No agent replacement is required by
   these schema changes. Check startup history/checksums and **both** kinds of
   calendar leases in addition to the existing runtime gate's scope.
7. Keep physical/action ingress paused. Personally review each historical button's
   gesture/device/room/action and explicitly save through Core with current
   `devices:update` + `devices:execute`. NULL grants remain inactive until this
   human action. No SQL backfill, bulk resave or inherited OWNER consent. V44
   disclosure and V45 destination consent are likewise explicit separate owner
   decisions. Then schedule real browser/provider and hardware acceptance separately.

## Rollback boundaries through V45

There is no SQL downgrade. Before any migration, retain the unchanged original
runtime/recovery set. After a partial migration, identify the actual committed
version and investigate with writers stopped. Prefer a reviewed roll-forward or
restore the **complete** pre-upgrade recovery set into a separate target. Do not
run V39/V41 code against V42–V45: Flyway future-version tolerance is not security
compatibility; old command claims can bypass provenance checks. Do not use V43 or
V44 binaries against V45 as an assumed safe fallback; select a reviewed
authority-aware artifact with the exact installed migration catalog and checksums.

A pre-upgrade restoration loses post-backup local events/disclosures/destination
generations/delivery history and all other writes. Keep the failed/post-upgrade
target sealed for reconciliation with both original audit histories intact. SQL
restore neither restores original keys/documents nor undoes device or Google
writes. Restore does not prove audit validity without the original key. Old-runtime
recovery restores the old authority gap and must remain isolated from action ingress.

A V45 restore preserves explicit DETAILS/AVAILABILITY disclosures, active and
revoked destination generations, ETags, copy IDs, attempted revisions, write-intent,
states and lease/fencing tokens. This is retention, **not renewed consent**. It can
resurrect permissions/consent revoked after the backup, restore an unexpired lease,
or forget a remote write after the backup. Keep user/provider/action ingress closed;
reconcile later revocations and remote effects before enabling reads or writes.
Do not replay RUNNING/NEEDS_REVIEW copies, clear leases by SQL, reset write intent,
silently overwrite remote edits or automatically opt in old destinations. Existing
manual per-target Core checks and conflict/review rules still apply after a
separately approved runtime start. Expired leases do not imply safe automatic retry.

## Reproduction and evidence boundary

```powershell
python -m unittest discover -s infrastructure/dev -p test_core_schema_migration.py -v
& infrastructure/dev/Test-CoreSchemaMigration.ps1 -JavaHome '<absolute JDK 21 directory>'
# Only in the coordinated stable source window:
& infrastructure/dev/Test-CoreSchemaMigration.ps1 -JavaHome '<absolute JDK 21 directory>' -FullCoreSuite
```

The runner accepts no operational target/credential/dump. It holds `core-checks.lock`
with FileShare.None throughout bootJar and tests, snapshots source/tool hashes,
copies an immutable artifact and passes it to the dedicated Testcontainers test.
Evidence/artifact stays under ignored `.run/dev-recovery/schema-acceptance/<id>/`.
The test uses real pg_dump/pg_restore from disposable PostgreSQL 17 only, never
an existing container or production connection. Its temporary credential files
contain only generated container credentials. No Spring context is used by this
rehearsal. The normal Gateway regression separately verifies runtime denial rules.

Open real gates: approved release provenance and ARM64 image, original-data/key /
document restore on each installation, protected agent/Voice target inventory,
quiet queue/lease disposition and window, actual Windows/Pi migration/activation,
individual old-button reviews, provider/browser/calendar acceptance with A and
physical button/Voice/radio/offline/reconnect acceptance. None is certified by the
synthetic schema-only tests.
