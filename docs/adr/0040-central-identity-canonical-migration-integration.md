# ADR 0040: Canonical central-identity migration integration

Status: accepted for source integration and isolated validation; no deployment.

During integration, committed master advanced from `fba7cbb` to `ce10573`.
It now owns V44 personal-calendar disclosure and ADR0037. Concurrent uncommitted
household-delivery work reserves V45/ADR0038 and is not imported. The isolated
Identity branch previously used a different V44 and ADR0037; its handover
explicitly records no production rollout. Current operational reports record
personal Windows/Pi histories below V42, not either V44. No runtime is migrated.

Keep committed master's V1–V44 **byte-for-byte unchanged**. Allocate the incoming,
unreleased Identity schema as a new additive **V46**, preserving its SQL bytes.
Preserve the former feature V44 byte-for-byte as a test fixture outside active
Flyway locations. It is historical evidence, not another active migration or an
automatic compatibility path. The Identity ADR becomes0039; this ADR uses0040.

Canonical fresh/upgrade tests cover V42, V43, calendar V44 and Identity V46 (V45
is reserved until its owner commits it). Before rollout, integrate that pending
lower migration and test the complete sequence; do not deploy V46 and later
silently enable out-of-order V45. Add a negative rehearsal showing that a database
with the old Identity-only V44 stops on Flyway validation with its tables/rows
unchanged. If any installation actually ran that feature history, it needs a
separate reviewed compatibility plan and protected backup, not checksum repair,
table dropping, a reset, or inferred identity reconciliation.

This resolves source numbering without modifying applied SQL or losing either
feature. No changes are made to master, foreign working trees, installer or
production databases. Merge the later master commits only in the integration
branch and rerun the full combined suites and real-service browser acceptance.
