# ADR 0061: Journaled single-host update transactions

Status: Accepted

## Decision

Reuse the existing signed download proofs, protected installation journal,
operational backup format, Core maintenance start and platform service managers.
An update is an explicit owner/host-administrator action, bound to one verified
manifest, source configuration, source schema and transaction UUID. No application
identity, Space or provider implementation is duplicated.

Persist the startup fence before stopping application writers. Native services
are stopped and disabled; only the database and a maintenance-only Core may run
before activation. Compose application containers are explicitly stopped and
use the existing unless-stopped policy; the installer refuses ordinary starts
while fenced. Keep the fence after interruption or failure. Reserve only fixed,
transaction-scoped paths and database names. Reconcile old/new file hashes and
directory switches instead of inferring success from a phase label.

Capture and verify an encrypted operational backup while writers remain stopped.
Also retain a local database template snapshot, with connections disabled, for
same-host recovery. It is protected by the existing database filesystem policy;
it does not replace encrypted portable backup. Keep original configuration and
payloads. No archived SQL or database functions are executed to recover data.
Recovery clones the reserved pre-update database, preserving the failed database
for inspection; original signed binaries are restored. Schema downgrade is never
attempted. The host identity and local accounts remain the same on an update.

Core owns the pre-update disposition of unfinished command executions and the
sealed audit record. The signed target maintenance entrypoint may prepare an
explicitly supported source schema without starting Spring or migrations.

Stage runtime inputs before application shutdown where possible. PostgreSQL major
changes are refused; initial native support also requires the same PostgreSQL
runtime version. Run target Flyway migrations only with maintenance mode enabled,
verify actual resulting schema and health plus a denied application probe, and
stop that Core before activation. Save the activation point before enabling normal
application startup. After that point, resume only startup/health; never silently
restore old data over possible new writes. Explicit recovery requires acknowledging
post-activation write loss and retaining the failed database and a new backup.

Manual resume and recovery do not depend on internet once the authorized runtime
inputs have been staged. Expiry is checked when authorization begins; subsequent
recovery uses the journal-bound proof and immutable digests rather than fetching
an unrelated new release. New update authorizations still require current trust.

This first coordinator is single-host. Distributed authority/version barriers and
automatic-window policy must be implemented separately before enabling unattended
distributed updates; do not report a successful single-host update as that proof.

Compose transactions also bind the root-owned Unix socket paths and Docker
daemon ID before staging. Resume and recovery refuse a different daemon, even
when another local context has a similarly named Compose project. A daemon
restart may replace its socket inode; that inode is not the stable identity.

## References

[Docker restart policy](https://docs.docker.com/engine/containers/start-containers-automatically/)
documents persistence of manual stops with unless-stopped.
[Docker system info](https://docs.docker.com/reference/cli/docker/system/info/)
documents the daemon ID and machine-readable format.
[PostgreSQL CREATE DATABASE](https://www.postgresql.org/docs/17/sql-createdatabase.html)
and [ALTER DATABASE](https://www.postgresql.org/docs/17/sql-alterdatabase.html)
define template cloning, connection exclusion and database renaming.
