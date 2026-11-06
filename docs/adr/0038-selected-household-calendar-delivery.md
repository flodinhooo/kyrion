# ADR 0038: Selected household calendar delivery

Status: accepted implementation direction for the first HOME-04 slice, 2026-11-06.

## Decision

Add manual, explicit Google delivery of saved native household events. Personal
visibility (ADR 0037) and permission to receive writes are independent. No existing
account, role, disclosure or event acquires a destination automatically.

Each credential owner opts into one actual writable Google calendar. This permits
active selected participants with calendar read/update permission to publish their
joint native events there, only while that credential owner is also an active
participant with calendar read/create/update permissions. OWNER cannot opt in on
someone else's behalf. Positive consent validates the current connection and
calendar; revocation requires no provider call. Destination changes and revoke /
re-enable use revisioned immutable grant generations; disconnect nulls the bound
connection, so a new connection never inherits consent. Retain old grant metadata
to explain previous deliveries without retaining credentials.

An editor explicitly selects recipients and confirms publishing the saved event.
Each HTTP request delivers one selected target; Web sequences requests and reports
per-target results. There is no background worker, implicit write on mount, local
edit, refresh or native event creation. Unsaved form changes must be saved first.
The caller must provide the current native revision and a server-issued grant ID;
provider calendar IDs, tokens, actor IDs and recipient identities are never accepted
as command authority. Every target is validated independently in Core.

V45 adds opt-in generations and delivery records. One copy per native event /
recipient / concrete connection-calendar pair has a deterministic Google-compatible
ID and private marker. Re-enabling the same destination reuses that copy, rather
than generating another one. Destination changes leave old copies intact and
visible in delivery history. Browser views contain usernames, opaque IDs, saved
revisions and machine-readable states, never provider IDs, ETags or credentials.

Short transactions under existing Space authorization locks validate and reserve
an attempt with a five-minute lease and random fencing token, and record audit.
HTTP runs outside transactions. Provider calls carry a mandatory expected
connection and authorization callback, including token-refresh retries. Before
each operation check current actor, participant, recipient, permissions, grant,
canonical revision, attempt and lease. After HTTP revalidate before declaring
success; superseded attempts cannot finalize newer records. A revocation blocks
subsequent operations, but cannot recall an already transmitted HTTP write.
Results affected by in-flight revocation/edit are explicitly NEEDS_REVIEW.

Read remote state first. Only the exact private marker can identify our own copy.
An unchanged stored ETag permits conditional PATCH; a matching desired copy can
recover a lost response without another write. Divergent external changes,
recurrence/all-day conversion, deleted confirmed copies and wrong markers are
conflicts. Record write intent before HTTP. After an uncertain first insert, a
missing remote copy requires review rather than automatic recreation. Stable IDs
prevent duplicate insertion. Provider errors preserve retry/review state; an
explicit retry is never permission to overwrite a conflict. No remote delete or
automatic provider-to-canonical merge is supplied.

Deleting a native event still requires its creator and matching revision. Block
deletion during a live delivery lease. If deliveries exist, require an explicit
`retainExternalCopies=true` acknowledgement: existing/uncertain provider copies
remain independent and will receive no later updates from that native event.
Record retained-copy audit atomically before deleting local tracking rows. This
conservative retention policy adds no personal calendar deletion authority and
does not imply that both participants may delete the native event.

## Limits

This slice supports timed native events through the existing Google adapter.
Remote edits are not merged, provider copies may appear in existing Google views,
and shared-source duplicate suppression is later usability work. A stopped browser
batch may have partial outcomes; refresh statuses before retry. An expired lease
can be retried safely under the remote version/marker rules; no queued command is
automatically resumed at startup. No AI/Voice authority, scheduler, other provider,
recurrence authoring, live write, migration or deployment is implied by source
delivery. Changes to participant membership and remote-copy deletion need separate
product decisions. An original-data V45 upgrade/restore drill remains a release
gate, distinct from the earlier Gateway rehearsal through V43.
