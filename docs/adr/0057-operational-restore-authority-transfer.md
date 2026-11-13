# ADR 0057: Operational restore and authority transfer

Status: accepted for implementation, 2026-11-13. Implementation and target
acceptance remain in the installer requirement matrix; this ADR is not evidence
that restore or automatic updates are complete.

Reuse the existing encrypted operational backup, signed runtime bundles,
installation journal, Core identities and Space/membership store. Never import
archived Compose files, executable settings or installation journals as active
host configuration. Generate host configuration from the reviewed bundle and
chosen target network settings, retain original credential/audit keys and
Knowledge data, and verify schema and account/Space/audit counts.

A target receives a new local host installation UUID. The logical Core accounts
and Space remain the restored data. Existing Core recovery rules determine the
local identity/recovery disposition; do not create another account system.

Before enabling the target writer, require a source-retirement receipt bound to
the exact encrypted backup digest and target UUID. Persist retirement intent
before stopping services, stop/remove owned Linux containers or stop/disable all
owned native services, and issue the receipt only after completion. Guards in
the installer and native service runner prevent accidental repair/restart of a
retired authority. Older source runtimes without this guard must be upgraded;
do not silently claim they are fenced. Receipt authentication uses a domain-
separated HMAC with the original protected audit key already in the encrypted
backup. It is an owner-authorized transfer receipt, not a public signature or
proof against a malicious administrator possessing the recovery material.

Retirement is monotonic. Repeated requests for the same backup/target resume;
requests for a different target fail. A failed target stays resumable and
inactive. Offline/lost sources without retirement proof allow inspection and
quarantined data preparation only, not an unproven competing active writer.
General disaster activation after irrevocable source loss needs a separately
reviewed identity disposition; never silently bypass retirement.

Restore targets start only PostgreSQL until data import and compatibility checks
complete. No household/provider action is part of restore testing. Partial data
imports must be discarded/recreated in the explicitly owned target before retry;
never merge into an existing application database. Do not promise schema rollback.

PostgreSQL explicitly warns that dumps can execute code chosen by their source
superuser, even for partial restores. Encryption authenticates possession of the
recovery passphrase; it does not make an arbitrary downloaded database safe.
Use isolated database execution and the existing least-privileged database OS
identity, never execute dump-derived shell commands as host administrator.

For full activation, new captures additionally contain binary COPY table data
and a bounded schema/migration/sequence descriptor. Build an empty target schema
using the signed Core release, require an exact descriptor match, then import
only binary row data into its existing tables. Do not execute archived DDL,
functions, triggers or pg_restore commands on the application target. Keep the
fresh signed Flyway history, validate all original target foreign keys after
loading, restore sequence positions, rotate host identity and revoke sessions.
Security/business disposition belongs to Core's local maintenance entrypoint,
not installer-owned SQL policy. Core re-verifies the transfer HMAC and existing
audit chains, applies revocation/identity changes transactionally and appends a
sealed restore event. The entrypoint starts no HTTP server and needs the target's
protected DB credentials and original audit key; a public receipt alone grants
no database access. The installer checks that the signed runtime actually
supports this capability before advertising a prepared target.

Compatible target releases may differ in version when PostgreSQL major, supported
Core schema, exact migration checksums and the complete fresh schema descriptor
match. A version string alone is not compatibility evidence. Initially only
PostgreSQL 17/Core schema 49 is accepted; later schema support needs explicit code
and tests. Changed schemas remain an update/migration concern after restore.
Legacy dump-only archives retain isolated verification; they require a new
portable capture before this activation path. This is a compatibility boundary,
not a claim that legacy arbitrary SQL has been made safe by partial restoration.

Configured local recovery material is installation-bound. During the same
authenticated Core disposition transaction, verify the restored protected host
key against its source-installation hash and rebind only its host hash to the new
installation identity. Keep old recovery codes/sessions invalid. A configured
recovery row without its matching protected key blocks activation; never silently
replace it or weaken ordinary recovery authentication. The Linux helper gets only
a read-only recovery-directory mount. Validate this with an actual interactive
host-tool provision/restore/rotate test, not merely copied file bytes.

Reference reviewed: [PostgreSQL 17 pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).
