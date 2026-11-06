# ADR 0035: Home membership and shared family calendar direction

Status: accepted product direction; implementation and schema design are planned.
Date: 2026-11-06.

## Context and decision

The owner prioritizes private households and families. Business expansion is
deferred; existing Business safeguards must remain intact. This decision changes
the intended product model, not the currently enforced single-Space runtime.

An account belongs to one identity type, HOME or BUSINESS. A HOME identity may
eventually join several HOME Spaces with different roles in each. HOME identities
must not be usable in BUSINESS Spaces. First installation creates the household
Space and its first OWNER atomically through the existing protected setup flow;
the OWNER may subsequently delegate roles, subject to existing owner protections.

Account identity, Space membership and membership roles are separate concepts
in the target model. The current immutable account `space_id` and compatibility
owner partitions are not silently converted or rewritten. Cross-installation
identity/trust is a separate future design: do not introduce a central account
service, shared passwords/tokens or federated login as part of the first calendar
slice. ADR 0031 remains the implemented runtime boundary until a reviewed,
additive membership migration and isolation acceptance supersede it.

A household calendar combines Kyrion-native shared events with voluntarily
shared personal provider calendars. Roles authorize features; explicit personal
grants authorize visibility and permitted writes to personal calendars. OWNER
does not automatically obtain another member's personal calendar or documents.
Presentation filters are separate from authorization.

The owner explicitly confirmed that both partners may edit a jointly created
event. In the general case, its active Space members selected as participants
may edit that shared event, subject to calendar permission. Personal source events
remain controlled by their source owner unless explicitly shared for editing.
Being an invited participant is not permission to write arbitrary events into
someone else's personal calendar or access their other events.

Each shared event has one canonical Core identity and revision; optional copies
in explicitly permitted participant calendars are linked deliveries, not new
unrelated Kyrion events. Updates keep the authenticated editor separate from the
personal connection owner. Core checks both before each external operation.
Provider failures cannot roll back already successful remote writes: record
per-target state, preserve conflicts, and retry idempotently without duplication.

## Consequences and boundaries

- The first implementation stays within one household/installation and the
  existing local identity/enrollment boundary. Multi-HOME membership and
  cross-installation login remain explicit later milestones.
- The calendar design must distinguish private, availability-only and detailed
  visibility; external shared-event delivery additionally needs owner opt-in and
  a selected writable destination. Hiding a calendar in the UI does not revoke it.
- Revocation must prevent future reads/writes and retries. Do not automatically
  delete existing remote events or claim to retract information already seen.
- Attendee removal, shared-event deletion, provider copy retention and conflicting
  edits require explicit behavior before those mutations are implemented.
- Existing Google account ownership and encryption, local shared-event behavior,
  audit history, keys and applied migrations must be preserved.
- Google, iCloud/CalDAV and other providers are distinct adapter work; a uniform
  iOS/Android Web experience does not prove universal calendar connectivity.
- No Business enablement, multi-Space guard removal, general resource ACL engine,
  calendar-to-calendar bulk mirroring or paid cloud dependency is introduced.

Implementation sequence and acceptance: [Home calendar plan](../home-family-calendar-plan.md).
