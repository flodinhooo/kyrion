# ADR 0044: Selected personal calendar recipients

Status: accepted implementation direction, 2026-11-09. Live schema/runtime
activation requires the separate operator rollout described in ADR 0040.

## Decision

Replace the audience of personal-calendar disclosures from ADR 0037 with an
explicit bounded list of active calendar readers in the same HOME. Only the
credential owner selects recipients, together with the existing privacy mode and
revision. Sharing does not grant editing or provider delivery rights. Positive
sharing requires at least one recipient; PRIVATE clears the list. A stale write
must not replace a newer audience. Changes are audited atomically.

Add V47 with a recipient relation bound to both disclosure and account Space.
Snapshot each existing positive disclosure to its current active household
accounts, excluding its owner. Read permissions remain checked at request time.
This preserves the existing eligible audience without granting access to future
members. Never modify V1–V46. New disclosures default to no recipients.

Source enumeration and individual event reads require recipient membership, active
same-HOME membership and calendar read permission before provider access and
again before returning. Removing a recipient while a provider request is in
flight discards that response. OWNER status never bypasses recipient selection.
Existing visibility redaction, no-store responses and browser invalidation stay.

Recipient IDs are returned only with the credential owner's settings. Shared
source responses do not reveal recipient lists, provider IDs or credentials.
The existing eligible household-member API supplies recipient names. Missing
recipient-capable settings from an older runtime must not offer a functional
recipient editor or silently fall back to sharing with everyone.

## Consequences

No provider write, new integration permission or AI access is introduced. This
is an additive schema and coordinated Core/Web rollout. Source tests and a
synthetic database rehearsal do not constitute live migration approval or real
Google/partner acceptance. Deactivated recipients cannot read; reactivation may
restore an unrevoked grant, consistent with existing role-revocation semantics.
