# Local database upgrade to V39

Date: 2026-10-30, approximately 23:11 Europe/Zurich. This follow-up was explicitly
requested by the user after source integration. It supersedes the V33 operational
checkpoint in [the integration report](final-integration-report.md), not the
remaining hardware, runtime-release or multi-Space acceptance gates.

## Applied operation

Target: existing local `kyrion-postgres` container, database `kyrion` on loopback
TCP5432. Successful history before upgrade was V1–V33. The validated combined
artifact's migration resources were extracted and matched against current source.
Flyway and PostgreSQL drivers came from that existing artifact; no dependencies
were downloaded. A standalone JDBC/Flyway entry point performed the operation:
no Spring application, HTTP listener, integration scheduler or new Core was started.

The six migrations were applied with `validateOnMigrate=true`, `group=true`,
`outOfOrder=false`, `cleanDisabled=true` and target39. PostgreSQL ran the migration
group transactionally. No repair/history manipulation or destructive data reset
was used. Active Calendar synchronization leases were checked to be zero.

| Version | Applied component |
|---|---|
| V34 | AI preferences, policy and usage |
| V35 | Personal memory/context controls |
| V36 | Personal Knowledge, ingestion/retrieval/source persistence and restrictive default grants |
| V37 | Personal calendar context opt-in |
| V38 | Canonical Home/Business Spaces and memberships |
| V39 | Business identity and protected local recovery schema |

Final Flyway validation: **39 successful migrations, no checksum mismatches,
no pending migrations**. All original33 version/checksum/success records remained
identical. One canonical existing HOME Space was created for the current root;
there was no multi-Space provisioning or inferred Business/email verification.

## Backup and rehearsal

Before any active migration, the existing backup tool created a custom-format
compressed dump under the standard external backup location:

`E:\Kyrion\Data\backups\postgres\upgrade-v39-20261030-230558\kyrion-postgres-20261030T220558Z.dump`

The new backup directory has inheritance removed and full access granted only
to the operator account and SYSTEM. The dump contains private data: do not attach
or commit it. Its manifest records SHA256 and `restoreVerified=true` after the
existing restore verifier successfully restored V33 and37 public tables into its
own temporary database. Keep audit/credential key files protected separately;
this database dump does not replace a key backup or complete Knowledge-file backup.
No Knowledge tables/originals existed in the starting V33 database.

A second disposable database was restored from this same real dump and upgraded
to39 before touching the active database. All36 pre-existing application tables
were checked using their original columns, excluding only Flyway history from
application-data comparison. Existing permission/catalog rows were verified as
preserved subsets because these migrations legitimately add permission rows.
Other existing table projections matched their pre-upgrade digests exactly.

The same36-table preservation check then passed on the active database, with
zero unexpected existing-table differences. Raw rows, credential values and
password hashes were not printed or included in this report.

The first rehearsal invocation stopped at explicit pre-migration `validate()`
because resolved pending migrations were not yet applied. The standalone helper
was corrected to use normal `migrate()` with validate-on-migrate, followed by final
`validate()`. The restored V33 database was unchanged by that initial failed check;
its successful rerun preceded the active migration.

Private operation evidence/helpers are under
`.run/dev-recovery/database-upgrade-v39/`, including rehearsal, live preservation
and post-upgrade Voice results. They are local operational scratch material, not
a new product migration API. Their `apply` action refuses a starting history other
than exactly V33 and must not be reused blindly for future upgrades.

## Runtime verification and limitations

- All seven local service readiness checks passed after migration: PostgreSQL,
  Core, Web, AI, Ollama, STT and TTS.
- The reviewed combined JAR passes the read-only runtime gate with39 installed
  migrations, no mismatches/pending entries and no active synchronization lease.
- Existing Core PID35108 remained running with the dedicated guarded Java
  executable. No Core restart or binary replacement occurred; no other service,
  WSL, Docker, Pi, firewall, DNS or Pi-hole configuration was changed.
- Pi-to-Core health and unauthenticated denial passed. An authenticated Voice
  session opened, returned a valid24-kHz greeting WAV and closed successfully
  using the existing process-local IPv4 diagnostic. These establish API/WAV behavior only, not acoustic
  playback, speaker identity or full acceptance of the new combined application.

**The database is current; the running Core binary is still the previously
accepted older artifact.** A separately controlled start of the combined binary,
preserving guarded LAN configuration, remains necessary to expose the newly
integrated application features. Do not confuse a current schema and healthy
existing Core with full K-Data/Spaces UI/runtime acceptance. All43 integration
TODOs retain their uncompleted live/security acceptance portions.

No new feature, production deployment or paid provider request was performed.
The owned rehearsal database and its temporary container dump were removed only
after successful active upgrade/acceptance; the external verified backup remains.
