# First HOME use: source readiness and operational acceptance

This checklist distinguishes implemented software from an activated installation.
The current development line is master, including native joint events, voluntary
personal disclosure, manual selected-recipient Google delivery and V45 tooling.
Historical source reports retain their own exact test/artifact evidence.

| Outcome | Current evidence | State |
| --- | --- | --- |
| Shared household event creation and joint editing | Explicit participants, revisions, creator-only deletion and Core isolation tests | Source verified |
| Voluntary personal read disclosure | Private / availability / details, connection-bound consent and in-flight revocation tests | Source verified |
| Selected personal destinations | Owner opt-in, explicit manual publication, per-target failure, ETags/idempotency, retention and revocation tests | Source verified |
| Calendar usability first slice | Confirmed own-copy merge, unchanged-time preservation across DST, spring-gap rejection and reachable long dialogs; isolated two-user browser flows | Source / browser fixture verified |
| Schema-only V45 path | Exact-artifact planning/apply; synthetic V39/V41/V43/V44 upgrades and V45 data restore, actual dump/restore, negative gates | Synthetic rehearsal verified |
| Recover the real installation | Original data plus original credential/audit keys, Knowledge/configuration; independent protected restore and retained revocations/effects | OPEN |
| Identify and activate the exact target | Fresh Windows/Pi history, protected Gateway/Voice destinations, pinned reviewed artifacts and ARM64 build where applicable, maintenance/writer fence | OPEN |
| Live household/provider acceptance | Disposable live Google data, real account/browser decisions, external edit/retry/disconnect/retention behavior | OPEN |
| Hardware acceptance | Explicit old button review/resave, visible/audible device/Voice outcomes, offline/reconnect/radio/recovery evidence | OPEN |

Read [Calendar usability](agent-handoffs/2026-11-06-calendar-usability-results.md),
[V45 migration results](agent-handoffs/2026-11-06-core-schema-v45-results.md),
[V45 operator sequence](core-schema-v45-rollout.md) and the
[Gateway rollout runbook](gateway-authority-rollout.md). Migration plan files do
not authorize a live apply. No productive upgrade, runtime restart, provider write
or automatic legacy button approval is claimed by the source work.

The earlier read-only runtime observations were Windows V39 and Pi V41. Recheck
them before activation; a passing source build does not establish a newer live
schema. Never restore just SQL and generate replacement keys, downgrade an old
binary against the new schema, or silently revive revoked consent/grants after
restoration. Preserve both audit histories and reconcile post-backup effects.

## Intentional follow-up product scope

Not a prerequisite for the initial bounded HOME use: new Business features,
multi-HOME/cross-installation identity, additional providers, recurring/all-day
authoring, automatic delivery and provider-copy deletion. These need separate
contracts/decisions. Multiple simultaneous private overlays and choosing between
both occurrences of a newly authored ambiguous wall time remain usability work.
Availability-only overlays retain their privacy boundary and may show separate
busy intervals; they are not an authoritative free-slot suggestion API.
