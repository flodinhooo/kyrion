# V40 rollout preparation — no active migration authorized

This is an operator procedure, not an automatic updater. The existing active
database/binary remain V39. Never run `bootRun`, start the newest build or let an
unreviewed helper select it against that database simply to expose new features.
The new startup gate refuses pending/mismatched migration histories, including
newV40→oldV39 and oldV39→newV40 binary/database combinations.

## Preconditions for a separately authorized rollout

1. Record installed migration versions/checksums, current binary/JDK SHA256,
   server configuration and pending Calendar sync leases. Pin the existing
   working binary separately from build output. Inventory in-flight/reserved/
   uncertain AI attempts. Do not clear reservations or retry generation to close
   them. Record the controlled outage and intended exact migration target40.
2. Quiesce **all Core writers/workers** for a consistent backup boundary; confirm
   no active integration leases or unresolved device execution. Stop only the
   scoped application processes, not unrelated Docker/WSL workloads. Preserve
   database, protected audit/credential keys, identity/bootstrap state, RBAC,
   memory/context settings and original Knowledge documents as one recovery set.
3. Use `infrastructure/postgres/backup.ps1` with a protected external destination.
   Preserve the dump's manifest/checksum and original keys separately. The
   restore verifier now requires the manifest before contacting any container;
   `pg_restore` success without checksum/evidence is not acceptance.
4. Restore to an isolated target first. Verify hashes,39 successful migrations,
   account/session/grants, conversations, confirmed memory/settings, audit-chain
   integrity using the original key, original document references and usage
   reservations. A database-only restore does not restore keys/documents or
   external provider state. Keep the known V39 recovery set intact.

## Rehearsal and migration boundary

The automated `CombinedMigrationIntegrationTest` uses only disposable
Testcontainers PostgreSQL and synthetic accounts/ledger data. It creates a V39
source, takes a real custom-format `pg_dump`, restores it to a second database,
applies/validates V40 there and checks identities, preserved charges/snapshots and
legacy pending→uncertain handling. The original V39 database remains unchanged
and validates as the rollback target. Only those owned temporary databases/dump
are cleaned up. Existing migration fixtures also test user/security/audit data
preservation and incompatible historical branches.

For an authorized real rehearsal, use the same boundary with the protected
backup and approved runtime artifact. Verify V1–V39 bytes unchanged; no Flyway
repair, downgrade, `clean`, state reset or blind branch-migration renumbering.
V40 preserves charges, adds snapshots and conservatively marks old pending
attempts `LEGACY_REVIEW_REQUIRED`; it does not recreate missing historical prices.

Only after successful restore/application checks, explicit operator approval and
a quiet writer window may the separate rollout apply exactly V40. Do not disable
the normal startup migration gate as an ad-hoc migration command. Review any
standalone migration entry point against the exact source version/target before
use; the earlier V33→V39 helper is not a V40 deployment tool.

## Postchecks and rollback

Validate40 successful migrations, zero checksum mismatches/pending entries and
unchanged data/audit/key/document ownership. Confirm conservative open cases,
price snapshots, same-turn replay denial, DE/EN usage inspection, local-only/
consent/budget gates, actor/Space isolation and one correlated audit transition
per real request. Test AI offline, cancellation, missing usage, late settlement,
restart and UTC-month behavior with isolated synthetic turns before resuming
ordinary traffic. Exercise the HTTP/1.1 AI compatibility and guarded Pi path
before calling Voice ready. Real cloud spending remains separately authorized.

An older binary is **not** assumed compatible with V40 merely because Flyway
allows a schema newer than its migrations. The read-only runtime gate rejects
that combination. Rollback means: stop V40 writers, preserve their new data for
reconciliation, restore the complete pre-upgrade recovery set into a separately
prepared V39 database/storage target, validate with the original keys and pinned
V39 binary, then deliberately switch the target. Never downgrade SQL in place,
launch the old binary against V40, overwrite the active database or delete the
failed-upgrade evidence. Document/reconcile writes and external effects after
the backup; a database rollback cannot undo provider charges/device effects.

Still open: protected real-installation backup/restore of the full recovery set,
interactive application rollback on the supported host and explicit migration/
deployment approval. This task tests synthetic data only and performs no rollout.
