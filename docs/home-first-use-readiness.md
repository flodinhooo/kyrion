# First HOME use: source readiness and operational acceptance

Latest actual operational checkpoint:
[owner-authorized Windows/Pi V46 rollout](agent-handoffs/2026-11-06-v46-live-rollout.md).
Both live schemas/runtimes are now updated; earlier V39/V41 observations below
are historical. Three legacy bindings per installation still require explicit
review/resave. Productive central-provider configuration remains optional/open.

This checklist distinguishes implemented software from an activated installation.
The current development line is master, including native joint events, voluntary
personal disclosure, manual selected-recipient Google delivery and V45 tooling.
Historical source reports retain their own exact test/artifact evidence.

| Outcome                                           | Current evidence                                                                                                                                                           | State                                                                |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Shared household event creation and joint editing | Explicit participants, revisions, creator-only deletion and Core isolation tests                                                                                           | Source verified                                                      |
| Voluntary personal read disclosure                | Private / availability / details, connection-bound consent and in-flight revocation tests                                                                                  | Source verified                                                      |
| Selected personal destinations                    | Owner opt-in, explicit manual publication, per-target failure, ETags/idempotency, retention and revocation tests                                                           | Source verified                                                      |
| Calendar usability first slice                    | Confirmed own-copy merge, unchanged-time preservation across DST, spring-gap rejection and reachable long dialogs; isolated two-user browser flows                         | Source / browser fixture verified                                    |
| Schema-only V45 path                              | Exact-artifact planning/apply; synthetic V39/V41/V43/V44 upgrades and V45 data restore, actual dump/restore, negative gates                                                | Synthetic rehearsal verified                                         |
| Recover the current real installation data        | Separate actual Windows/Pi dumps independently restored, original audit/credential keys verified, configurations preserved; both datasets contain zero Knowledge documents | Verified for current datasets; retain recovery/reconciliation gates  |
| Identify and activate the exact target            | Live V46 on both installations, original data/role digests retained, reviewed Windows/ARM64 runtimes, protected routing/HTTPS and fresh Pi heartbeat                       | Activated; healthy runtime and anonymous DE/EN browser checks passed |
| Live household/provider acceptance                | Disposable live Google data, real account/browser decisions, external edit/retry/disconnect/retention behavior                                                             | OPEN                                                                 |
| Hardware acceptance                               | Explicit old button review/resave, visible/audible device/Voice outcomes, offline/reconnect/radio/recovery evidence                                                        | OPEN                                                                 |

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
