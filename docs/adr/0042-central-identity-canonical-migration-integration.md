# ADR 0042: Canonical central-identity migration integration

Status: accepted for source integration and isolated validation; no deployment.

During integration, committed master advanced from `fba7cbb` to `ce10573`.
It now owns V44 personal-calendar disclosure and ADR0037. Household delivery then
committed as `e3d9ff4` with V45/ADR0038 and is also integrated. The isolated
Identity branch previously used a different V44 and ADR0037; its handover
explicitly records no production rollout. Current operational reports record
personal Windows/Pi histories below V42, not either V44. No runtime is migrated.

Keep committed master's V1–V45 **byte-for-byte unchanged**. Allocate the incoming,
unreleased Identity schema as a new additive **V46**, preserving its SQL bytes.
Preserve the former feature V44 byte-for-byte as a test fixture outside active
Flyway locations. It is historical evidence, not another active migration or an
automatic compatibility path. The Identity ADR is 0041; this ADR is 0042, preserving master's
0039 calendar presentation and 0040 schema-only migration decisions.

Canonical fresh/upgrade tests cover the complete V1–V46 sequence, including V42,
V43, calendar V44, household delivery V45 and Identity V46. No lower-version gap
remains. Add a negative rehearsal showing that a database
with the old Identity-only V44 stops on Flyway validation with its tables/rows
unchanged. If any installation actually ran that feature history, it needs a
separate reviewed compatibility plan and protected backup, not checksum repair,
table dropping, a reset, or inferred identity reconciliation.

This resolves source numbering without modifying applied SQL or losing either
feature. The owner subsequently authorized integration into master after chats A/B
closed. Preserve all existing master and Identity source and rerun combined
suites and real-service acceptance there. Installer, production databases and
operational activation remain outside this source integration.
