# Artifact-bound V45 schema migration results (Chat B)

Status: implemented, synthetically verified and committed; no operational apply authorized.
Baseline: clean `master e3d9ff4ca3b1a72b858197d4c1e6825ecf988bd6`.
Decision: [ADR 0040](../adr/0040-artifact-bound-schema-migration.md).
Operator sequence and commands: [V45 rollout](../core-schema-v45-rollout.md).

## Delivered scope

The standalone migration tool closes the earlier missing schema-only apply path.
It uses the Flyway/JDBC/JSON support libraries and exact V1–V45 SQL from a
SHA-256-pinned Core boot JAR. No Spring/application classes or configuration are
loaded, and no queue, scheduler, device or provider path is started. No new
dependency, SQL migration or Core build configuration is introduced.

Default planning is server-enforced read-only. A later Apply requires the reviewed
plan bytes/hash, exact artifact/catalog/tool hash, actual target identity and
unchanged source history/data/sequence fingerprints. The target binds PostgreSQL
cluster identifier, database OID/name, server address/port and authenticated role.
No root-owner fallback or arbitrary JDBC/SQL/target-version option is supplied.
Unexpected catalogs, checksum/history corruption, different targets, changed data,
other client sessions and concurrent tool runs fail closed. The session/advisory
checks do not replace an operator-enforced outage/writer fence.

Credentials are loaded from a protected non-Git JSON file and passed on child
stdin. They are absent from process arguments, plan/result output and diagnostics.
Third-party errors are captured and replaced with machine codes, not printed with
SQL/row values. Remote connections require verified TLS; the explicit plaintext
exception is for loopback only. An immutable artifact's independently approved
hash and protected operator/tool files remain prerequisites, not something this
tool can self-certify.

Owned paths only: new ADR 0040, new V45 runbook, `infrastructure/dev/` Python and
Java tools, the PowerShell synthetic runner, offline Python rejection tests and
the dedicated `security/CoreSchemaMigrationRehearsalTest.kt`. This report is a
separate owned document. Existing V1–V45, calendar/Google/Web, Auth/RBAC, shared
tests/build configuration and overview files were not modified by B.

## Rehearsal design and findings

- Four independent disposable PostgreSQL 17 sources, with real Flyway histories
  through V39/V41/V43/V44, are seeded with synthetic accounts, a disabled member,
  assigned roles/permissions, a revoked session, integrity-chain/audit bytes,
  integration ciphertext/nonce/version metadata, nodes, commands and bindings.
  Real custom-format `pg_dump` / `pg_restore` create independent candidate and
  pre-upgrade rollback databases. The actual CLI plans and applies V45 using the
  immutable copied boot JAR; it never invokes the application.
- Existing history rows/checksums and protected logical data remain identical.
  V39's synthetic pending AI attempt correctly becomes `uncertain` with
  `LEGACY_REVIEW_REQUIRED`, preserving its charge/reservation per actual V40 SQL.
  V42 invents neither historical command provenance nor button approval. Already
  attributed commands and a disabled configurator's binding generation remain
  byte-identical, not refreshed. Legacy malformed `[]` remains a pending row
  awaiting fail-closed handling by the separately tested authority-aware runtime.
- V44 introduces no disclosures for existing Google connections. An explicit
  PRIVATE tombstone at V44 retains its revision. V45 creates no automatic
  destination or delivery. Source and rollback copies remain at their original
  versions/data, independently of candidate writes after upgrade.
- A fifth independent V45 data set contains PRIVATE/AVAILABILITY/DETAILS modes,
  active and revoked/unbound destination generations, household events and
  participants, all six delivery states, ETags, attempted/delivered revisions,
  write intent, attempt fencing and both unexpired/expired lease metadata. Its
  real dump restores into a different database; every public-table digest is
  identical and a freshly reviewed V45 Apply executes zero migrations, preserving
  all delivery states. The original target's plan is rejected on the clone.
- Negative integration cases reject changed account authority, another target,
  a competing client session, a wrong installed checksum, failed history and an
  empty uninitialized schema. Offline tests reject wrong artifact hashes,
  missing/future/duplicate migrations, callbacks/path traversal, plan tampering,
  missing explicit approval, mismatched plan artifact/target and remote plaintext.

Synthetic metadata is not original-key cryptographic verification. No live
database/dump is accepted by the test runner. Only owned Testcontainers and their
generated credentials are used. No test calls a real command-claim/provider API.

## Verification and commits

Source commit: **`209217aad29c9d68d7bff3f90ba731a1c1773303`**, exactly the seven
owned source/tool/runbook paths listed above. This report is committed separately;
its commit is available through `git log -- <this-file>` and the delivery message.
No branch/worktree/reset/stash, shared overview edit or foreign staging occurred.

Final frozen full acceptance: **422 Core tests, zero failures/errors/skips**,
fresh `bootJar` and compilation successful. The test task took 5m29s; the whole
locked build/test/evidence window was 2026-11-06 14:09:13–14:15:06 UTC. Includes
MigrationRehearsal6, GatewayAuthority28, HouseholdDelivery30, Household10,
Disclosure13, Google HTTP5 and all remaining suites. Source/tool SHA-256 manifests
were unchanged throughout and were rechecked immediately before the source commit.
The runner held `core-checks.lock` for the complete bootJar + tests; source staging
and commit then held the separate non-nested `git.lock`, both FileShare.None.

Evidence directory (ignored, local):
`.run/dev-recovery/schema-acceptance/431da2a67e9842beb11a99951e21ae11/` contains
`evidence.json`, `build.log`, `test.log`, source-before/after manifests and the
immutable candidate `reviewed-core.jar`. Exact artifact SHA-256:
`4dd4928e2dd1e3b4076d073edece4d0b5621b62cc4d4181d14b746c69b77de42`.
The real CLI extracted exactly V1–V45 from those bytes and used the artifact's
Flyway **12.4.0** and PostgreSQL JDBC **42.7.11**. JDK21 was the existing ignored
local toolchain; Python was 3.12. No artifact was started or installed.

The tested source was baseline `e3d9ff4` plus B's seven files and A's frozen,
then-uncommitted `calendar/HouseholdCopyLinks.kt` and six additional delivery
regressions in `HouseholdCalendarDeliveryIntegrationTest.kt`. These A paths were
neither staged nor committed by B. **The candidate is therefore not represented
as a pure build of B's source commit or an approved release artifact.** Its exact
bytes and full source manifests identify the rehearsal; production provenance
must be reviewed against the final integrated source/artifact independently.
A may resume Core work after the source commit; later edits need their own checks.

Additional verification:

```powershell
python -m unittest discover -s infrastructure/dev -p test_core_schema_migration.py -v
python -m unittest discover -s infrastructure/dev -p test_gateway_rollout_gate.py -v
& infrastructure/dev/Test-CoreSchemaMigration.ps1 -JavaHome '<absolute JDK 21 directory>' -FullCoreSuite
```

The new offline suite passed **11** cases; the unchanged existing compatibility
gate passed **6**. Ruff check and format-check passed for both new Python files;
PowerShell AST parsing passed; owned staged diff check passed. Kotlin/Java
compilation and the actual standalone javac invocations passed. No dedicated Core
formatter/linter task is configured. B changed no Web paths and claims no new Web
check; A owns that acceptance. Existing Gradle/JVM/Kotlin warnings were non-failing.

Diagnostic history retained separately, not counted as final acceptance:

- `3f108bbd773a4025b9c5cfde3a3302dd`: relative JAVA_HOME failed before compilation;
  the new wrapper now resolves it to an absolute path.
- `c785ec45521f4b7b8e3c6a6232663848`: the new standalone Java had an ambiguous
  empty-varargs Flyway overload, caught by all six new tests and corrected.
- `89bc673df2f445c0805d765bbd3a84f3`: V45 restore/no-op passed, older starts were
  rejected by standalone `validate` for planned pending migrations. Configuration
  now allows **only pending** entries and removes default future tolerance; the
  tool still requires contiguous successful installed history and an exact catalog.
- `0dc202ef99054b21aea74c51cefac0e1`: owned disposable PostgreSQL container startup
  timed out before the migration tests. Its startup budget is now two minutes;
  no existing service/container was stopped or reconfigured.
- `d62219b938d149e28055d06905ef6fbc`: focused34 + bootJar passed with stable sources
  before final per-Flyway-connection target verification and stricter extraction.
  The full422 run above tests those final changes, not just this earlier subset.

## Remaining real gates

Windows V39 and Pi V41 are prior read-only observations, not a fresh statement
that either is now at V45. This task makes no live connection to either database
and applies no operational migration. The intended target must be re-inventoried
before a real maintenance window.

OPEN: independently approved release/catalog and ARM64 image; protected original
data + original key/audit/document restore on both installations; protected agent
and Voice destination inspection; quiescent queue/lease disposition and writer
fence; separate live migration/startup approval; personal explicit review/save of
each old button; Calendar/provider/browser acceptance with A; physical
button/Voice/radio/offline/reconnect outcomes. No success follows from synthetic
tests alone. Rollback requires a separate complete recovery target, cannot undo
external writes, can lose post-backup history and can resurrect revoked consents.
Keep both audit histories intact and all action/provider/user ingress paused
through explicit revocation/effect reconciliation. No automatic grants or retries.
