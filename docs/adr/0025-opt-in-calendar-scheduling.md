# ADR 0025: Opt-in scheduled calendar synchronization

Accepted 2026-10-19 for Windows integration acceptance.

Extend ADR 0024 with a per-account, explicitly enabled schedule for already mapped
local timed events. Defaults remain disabled, including existing installations.
The UI states that enabling the schedule permits external writes and pending
deletions for those linked events. Unmapped local events never export.

Use Core's existing scheduler. Manual and automatic runs share a persistent
per-account lease, the same synchronization engine and current RBAC checks.
Persist interval, attempts, outcomes, failure count and next retry. Transient
failures back off; rate limits also gate manual retries. Conflicts remain intact.
An expiring lease provides crash recovery; renew it between event operations.
Disable scheduling in acceptance tests and never enable it for a live account
without the user's explicit action.

The browser refreshes the selected live range while an enabled schedule is being
viewed. This imports new external events for display without exporting them or
creating a second provider reconciliation mechanism. Recurrence and all-day
write restrictions remain unchanged.
