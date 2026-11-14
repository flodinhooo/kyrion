# ADR 0079: Verify native backups through an inactive disposable database

Status: Accepted for implementation, 2026-11-14.

Extend native maintenance using the owned installation's verified PostgreSQL,
portable binary-row importer and signed Core migrations. Do not execute archived
SQL or pg_restore against a running installation. A fresh random verification
database is created from template0 on the verified loopback-only owned cluster.
No Core HTTP server, scheduler, integration or device action runs against it.

Core provides a narrow non-Spring migration entrypoint restricted to loopback
URLs and generated verification database names. It executes only packaged
Flyway migrations into an empty public schema. The importer must match the
resulting schema descriptor, import rows, validate foreign keys and check
recorded counts before database verification is reported. Unsupported archive
schemas fail explicitly. A verified archive alone is not database acceptance.

The installation lock excludes updates/restore and existing authority fences
remain enforced. A private journal records name, expected cluster and database
OID. Cleanup targets only that identity. A creation interrupted before OID
acknowledgement is an explicit ambiguous resource requiring review, never a
reason to drop a same-named unproven database. Plaintext stays in protected
scratch. Existing application services and the live application database remain
untouched. This operation requires installed native runtimes; verifying before
any installation remains a separate future capability.

The documented [Flyway Java API](https://documentation.red-gate.com/flyway/reference/usage/api-java)
is already supplied by Core's dependency set. PostgreSQL 17's
[template0 creation contract](https://www.postgresql.org/docs/17/sql-createdatabase.html)
provides a clean schema without cloning a live application database. No new
dependency or alternative backup format is introduced.

Temporary imports use the installation's protected PostgreSQL storage, including
its normal WAL retention. Dropping the disposable database is not a promise of
secure erasure. No verification database is activated as a second installation.
