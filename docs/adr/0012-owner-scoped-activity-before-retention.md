# ADR 0012: Owner-Scoped Activity Before Retention

- Status: Accepted
- Date: 2026-08-22

## Context

Conversations and personal memories already have explicit owner lifecycles, but
the first activity-log slice stored installation-wide events without a separate
owner column. `actor_id` cannot safely substitute for ownership: an actor may be
a gateway, Voice Satellite, integration or AI component acting for an owner.
Applying owner-specific retention to that data would risk exposing or deleting
another future household member's records.

Retention is destructive once enforcement begins. Kyrion therefore needs a
stable ownership boundary before it can offer expiry or cleanup settings.

## Decision

Activity events gain a separate nullable `owner_id`. It identifies whose
Kyrion data or capability the event concerns and is independent from actor
identity. Core derives it for authenticated user events and requires services
acting for an owner to pass it explicitly.

Authenticated activity reads return only events for the authenticated owner
plus installation-level events whose category and actor are both `SYSTEM`.
Unowned integration, security or AI events are not exposed through an owner
feed. Existing user-actor events with a valid local account identifier are
backfilled; ambiguous legacy events remain unowned instead of being guessed.

The owner identifier remains internal and is not added to the browser response.
Retention enforcement is deliberately deferred. Until an owner selects and
confirms a future policy, conversations, activity events and confirmed memories
remain stored, while their existing explicit deletion paths continue to work.

Future household roles may grant a household administrator access to selected
member or installation events, but that permission must be explicit and must
not weaken this storage boundary.

## Consequences

- Activity feeds no longer rely on actor identity for data ownership.
- Gateway, Voice, integration and AI actions can remain attributable to their
  real actor while still being scoped to the affected owner.
- Retention policies can later calculate and delete owner data without mixing
  future household members.
- Installation-level system events remain visible to authenticated owners.
- Ambiguous historical non-user events may disappear from the owner feed; this
  is safer than assigning them without evidence.
- Automatic expiry, archival, legal holds and tamper evidence remain separate
  follow-up work.
