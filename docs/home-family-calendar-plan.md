# Home Spaces and family calendar implementation plan

Status: planned; owner-confirmed requirements recorded on 2026-11-06.
Decision: [ADR 0035](adr/0035-home-membership-and-family-calendar-direction.md).
Parallel ownership: [two-chat coordination](agent-handoffs/2026-11-06-parallel-home-and-gateway.md).

## Confirmed behavior

1. Prioritize HOME; defer new Business features while retaining its protections.
2. Protected first setup creates the household and its OWNER. Roles can be
   delegated with the existing permission ceilings and last-owner protections.
3. Eventually allow one HOME identity to join several HOME households, with
   per-membership roles. Never allow it into BUSINESS. Cross-installation login
   and the current single-Space restriction require separate reviewed work.
4. Each member voluntarily connects and shares selected personal calendars.
   Other members do not gain access merely because they are installation OWNER.
5. Show one household calendar with participant/calendar filters. Freely changing
   a display filter never changes another member's disclosure permission.
6. Create Kyrion-only household events or choose one/many participating members
   and explicitly permitted provider destinations. "Everyone" means an explicit
   server-validated participant list, not all accounts globally or future members.
   Missing write grants must be visible; never silently claim delivery succeeded.
7. Both partners may edit their jointly created event. Generalize this to active
   selected household participants with the required calendar permission.
   Permission to edit that event does not grant control of personal source events.
8. External calendar credentials remain personal and server-side. Shared edits
   go through Core's validated event/delivery model, never another member's token
   exposed to the browser or an unrestricted provider proxy.

## Milestones and acceptance

| ID | Complete slice | Acceptance |
| --- | --- | --- |
| HOME-01 | Specify calendar contracts, privacy and event lifecycle | Concrete request/response/error/state models; decide deletion, participant removal and copy retention before mutation implementation; record migration/data-preservation plan. |
| HOME-02 | Kyrion-native shared event participants and joint editing | Two household members can create/read/edit a joint event; stale revisions conflict; a nonparticipant cannot edit merely because they can see the household calendar; foreign households cannot read/write; deactivated membership and revoked permissions deny access. Changes audit actual actor and Space. Existing local events retain their existing shared behavior without reclassifying private data. |
| HOME-03 | Voluntary personal-calendar visibility | Owner controls private / availability-only / details; UI filters are independent; redaction is enforced in Core list/detail/context paths, not only the browser. Revocation removes future access and cached authorized representations. |
| HOME-04 | Selected-recipient provider delivery | Each target owner opted in and selected a writable calendar; canonical shared event plus per-target status, revisions/ETags and idempotency; participant editor and credential owner are separate; partial failure, retry, edits and revocation are tested. Start with existing Google adapter. |
| HOME-05 | Calendar usability and real acceptance | DE/EN, month/week/day, DST, timezones, all-day boundaries, offline/provider failures, external edits, duplicate suppression and disposable live-provider tests. Series/all-day authoring and further providers are separate scoped decisions. |
| HOME-06 | Multiple HOME memberships | Separate account/membership/role scope, safe current-Space selection and complete isolation; reviewed migration, no implicit resource movement. Cross-installation authentication remains its own milestone. |

HOME-02 is the recommended first implementation after HOME-01. It delivers a
jointly editable household event without relying on another person's OAuth grant.
Provider destination delivery follows only after personal grant semantics exist.

## Design questions still open

These are not already approved features or reasons to invent provider writes:

- May every participant delete a joint event, or does deletion need a different
  role/confirmation? Joint edit consent alone does not answer destructive deletion.
- What happens to a removed participant's previously delivered provider copy?
  What happens when a shared event is deleted or its creator leaves the household?
- How should new provider-side edits to linked copies reconcile to the canonical
  event? Preserve conflicts until a bounded policy is agreed.
- Should availability-only calendars contribute to conflict/free-slot suggestions?
- Which calendar services, recurrence features, reminders and mobile interactions
  should follow the first slice? Do not promise iCloud/CalDAV before adapter work.

## Current implementation conflicts to resolve explicitly

Accounts currently have one immutable Space membership; this is not multi-HOME
identity support. Local events are workspace-shared; Google connections and linked
sync actors are personal. Existing linked sync refuses another account's provider
connection. Do not remove that check to implement joint editing: introduce a
Core-owned shared event and explicit target authorization instead.

No schema or runtime behavior changes are delivered by this plan. Never edit
V1-V41 or migrate the running V39 Windows database implicitly. Existing Pi V41
and Windows V39 are separate runtime targets, each needing deliberate deployment.
