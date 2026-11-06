# ADR 0037: Voluntary personal calendar disclosure

Status: accepted implementation direction for HOME-03, 2026-11-06.

## Context

Native household events permit joint editing. Personal Google connections remain
owned by their connecting account. Neither household membership nor OWNER status
authorizes reading another account's calendars. HOME-03 needs voluntary visibility
before HOME-04 may introduce separately authorized provider writes.

## Decision

Add an explicit, default-private disclosure per actual Google connection and
calendar. Only its authenticated credential owner can change it. Modes are
PRIVATE, AVAILABILITY and DETAILS, shared with current active calendar readers in
the same active HOME Space. The UI explains this audience before saving. This
slice does not implement per-recipient ACLs or provider write grants.

Use additive V44 with composite account/Space and connection/account foreign keys.
Bind disclosure to the connection ID, never a mutable display name or `primary`
alias. Disconnect cascades disclosure deletion; reconnecting a new connection
requires new consent. Do not migrate existing personal calendars into shared data.
Updates require an explicit revision; stale settings conflict. A private setting
is retained as a revisioned tombstone until its connection is removed.

Expose selected shared source IDs and account usernames, not provider calendar IDs,
calendar names, emails or credentials. An availability response contains opaque
event IDs and time boundaries only; no title, description, ETag, recurrence identity
or provider marker. DETAILS adds only title and description. Shared events are
read-only. Personal direct reads and legacy linked synchronization stay unchanged.

Check actor, source owner, Space, calendar permission, connection and disclosure
before provider reads and again before returning. Perform provider HTTP outside
transactions. Final authorization/redaction uses the current setting in a short
transaction serialized with role/disclosure changes. Downgrading during a read
must never return old details. A changed revision discards the in-flight result.
No shared provider representations are persisted or cached. HTTP is no-store;
Web clears old shared data before refresh and polls while visible. Revocation
blocks subsequent requests; it cannot erase information already seen or copied.

The first slice selects one shared source at a time in the combined calendar.
All-day dates retain their exclusive end boundary. Availability conservatively
shows event intervals; it is not yet an authoritative free/busy scheduling API.
No AI/Voice context integration, provider mutation, recurrence authoring or live
rollout is included. Future context consumers must call this redacted boundary;
they must not fetch another member's Google data directly.

## Consequences

Sharing requires deliberate consent and appropriate role permissions. Removing
read access from either account suppresses subsequent shared reads. OWNER cannot
override disclosure. Re-enabling permissions can restore an existing opt-in;
disconnect or setting PRIVATE is the explicit permanent revocation mechanism.
The existing single-Space account model is preserved. Live provider acceptance
and selected-recipient writes remain separate work.
