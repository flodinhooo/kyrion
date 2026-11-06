# ADR 0040: Artifact-bound, schema-only migration

Status: accepted for implementation, 2026-11-06. No operational apply authorized.

Follow-up: the owner separately authorized the recorded
[Windows/Pi V46 live rollout](../agent-handoffs/2026-11-06-v46-live-rollout.md).
The integrated tool accepts exact V1–V45 or V1–V46 catalogs and explicitly binds
target45/46 in the plan. Cross-JVM snapshots execute transaction-local UTC
normalization because JDBC startup TimeZone can override datasource options.
The real PostgreSQL UTC/Zurich regression failed before and passed after this
fix; existing SQL and database timestamps are not changed. Future operations still
require their own target/recovery/maintenance approval.

## Decision

Use a separate Python/JDK 21 operator tool. Verify an explicitly supplied SHA-256
of an immutable reviewed Core boot JAR before extracting only its V1–V45 SQL and
allowlisted Flyway/JDBC/JSON support libraries into temporary storage. Compile a
small standalone Java entry point against those libraries. Never load application
classes, Spring, application configuration, callbacks, schedulers or provider code.
Use the artifact's Flyway implementation for validation, checksums and migration;
never manufacture or repair schema history. No new runtime dependency is required.

Default execution is a read-only plan. Apply requires the reviewed plan's hash,
artifact hash and target identity, and rechecks the complete public-table data
fingerprint and successful contiguous Flyway history before migration. Identity
includes PostgreSQL cluster system identifier, database OID/name, server address /
port and authenticated role. Credentials enter via a protected operator JSON file
and child stdin, never command arguments or output. TLS defaults to verify-full;
explicit plaintext is restricted to loopback disposable targets.

The tool rejects unexpected catalogs, future/missing/failed history, drift,
different targets and concurrent tool runs. Apply also rejects competing client
database sessions.
It does not stop writers: an operator-controlled maintenance window remains
mandatory. The advisory lock coordinates this tool only. The plan is a reviewable
binding, not a signature or a substitute for artifact provenance, original-key
restore, outage approval or protection of the operator account and plan files.

## Consequences

Windows and Pi can use the same schema-only path with separate recovery sets and
target-bound plans. A restored database has a new identity and requires a new
plan. No `clean`, `repair`, baseline, downgrade, SQL filtering, credential export,
automatic consent or startup is supported. V45 restore retains consents and
uncertain delivery states; restoration can resurrect revoked authority and cannot
undo provider/device effects. Synthetic rehearsals establish technical behavior,
not real-data/key recovery or hardware acceptance.
