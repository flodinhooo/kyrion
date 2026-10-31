# ADR 0033: Combined development migration history

Status: accepted for source integration and isolated validation, not live rollout.

The inspected local `kyrion-postgres` database has successful V1–V33 only; no
Knowledge or canonical Space tables exist. All checksums are retained. Feature
handoffs state Spaces V37/V38 ran only in disposable tests. No non-test V36
application was identified. Other installations must inventory their history
before using this source; this decision is not permission to repair their history.

Keep V1–V35 and the existing calendar-context V37 unchanged. Adopt the tested
K-Data completion's V36 rather than its earlier unshipped broad-grant variant:
new grants follow existing personal-memory permissions and do not expand a
restricted role. Assign the incoming, locally unapplied Spaces migrations V38
(Spaces) and V39 (Business identity/recovery), preserving their SQL contents.
No executed migration is renumbered in the inspected runtime database.

Validate fresh creation and upgrades from V30/V33/V34 on disposable PostgreSQL,
including users, role restrictions, ciphertext, calendar data, audit and personal
context controls. An installation with either incompatible V36 or branch-specific
Spaces V37/V38 must stop on Flyway validation: no automatic repair, checksum
overwrite, out-of-order migration or inferred data reconciliation is allowed.
Such histories require a separately reviewed additive/compatibility plan and a
verified backup. This sprint does not mutate the active database or replace Core.

Personal Knowledge remains actor-owned. Spaces RBAC must validate current active
membership for human calls, and ingestion must recheck actor/Space authority
before reading content, local embedding calls and publication. Preserve cloud
document denial, unverified-speaker restrictions, Business Voice/proposal guards
and the single-Space startup guard. Multi-Space runtime remains unsupported.

The newer committed public website tree is preserved byte-for-byte; the incoming
Spaces website presentation/tests remain in its original branch rather than
overwriting the independently developed website. Platform UI integration proceeds.
