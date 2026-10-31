# ADR 0034: Durable AI invocation and conservative usage reconciliation

Status: Accepted for implementation, 2026-10-31.

Core retains the existing per-account usage ledger and transactional budget locks.
Add an invocation fence and immutable reservation/pricing snapshots to that
ledger. Only a pending reservation may begin provider processing once. Invocation
is committed before network I/O; an interruption between those steps is uncertain,
never evidence that processing was free. No automatic retry/refund follows it.
Legacy pending rows become uncertain because their invocation cannot be proven.

Pending, invoked, uncertain, estimated, reported and rejected remain separate
states. Monetary amounts are always estimates, including when token usage is
provider-reported. Unknown prices remain null. Mixed known/unknown aggregates
remain unknown; monetary limits fail closed for unknown or incompatible currency
amounts. Reservation period and pricing never change during later settlement.

Complete, validated server-observed terminal usage may settle an uncertain or
estimated attempt later. A conditional transition updates it once with a correlated
audit event. Identical replay is a no-op; conflicting terminal evidence preserves
the first counters, restores a conservative token floor, marks monetary cost
unknown and opens a durable `USAGE_CONFLICT` investigation once. Further reports
cannot silently close that dispute. Settlement serializes with account budget
reservations. There is no browser endpoint for submitting totals or refunding
attempts, no billable reconciliation request and no new provider lookup service.
Current adapters do not offer durable billing lookup; unresolved attempts remain
visible across all periods and require investigation, without direct SQL refunds.

Additive V40 stores snapshots and invocation time; applied SQL is unchanged.
Tests use disposable databases. Deployment/migration of the active installation
is explicitly excluded from this task. Existing cloud-consent, account/Space,
satellite-speaker and Core action-authority boundaries remain in force.
