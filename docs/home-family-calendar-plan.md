# Home Spaces and family calendar implementation plan

Status: HOME-01 contract specified and HOME-02 native source implemented/tested;
HOME-03 Google disclosure and the first HOME-04 manual Google delivery slice are
implemented/tested. A first HOME-05 usability/source/browser-fixture slice is
verified; live household/provider acceptance and HOME-06 remain open.
No runtime rollout. Owner-confirmed requirements
recorded on 2026-11-06.
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
| HOME-03 | Voluntary personal-calendar visibility (Google first slice implemented/tested) | Credential owner controls private / availability-only / details; UI filters are independent; Core enforces redaction. No new context consumer was added; future consumers must use this boundary. Revocation blocks subsequent reads and Web clears prior authorized representations; already seen/copied information cannot be recalled. |
| HOME-04 | Selected-recipient provider delivery (manual Google slice implemented/tested) | Each target owner opts in and selects a writable calendar; participant editor and credential owner are separate. Explicit manual delivery of saved revisions has per-target status, ETags, stable copy identity, conflict/uncertainty handling and revocation. Native deletion requires explicit copy retention. Automatic delivery and provider-copy deletion remain separate. |
| HOME-05 | Calendar usability and real acceptance (first source/browser-fixture slice verified; live acceptance open) | Confirmed own-copy merge, DE/EN month/week/day controls, unchanged-time/DST preservation, spring-gap rejection and scrollable dialogs are verified. Availability privacy is not weakened for deduplication. Disposable live-provider/family acceptance remains open; recurrence/all-day authoring and further providers are separate. |
| HOME-06 | Multiple HOME memberships | Separate account/membership/role scope, safe current-Space selection and complete isolation; reviewed migration, no implicit resource movement. Cross-installation authentication remains its own milestone. |

HOME-02 is the recommended first implementation after HOME-01. It delivers a
jointly editable household event without relying on another person's OAuth grant.
Provider destination delivery follows only after personal grant semantics exist.

## HOME-01 implementation contract (first native slice)

The first slice adds a separate Core-owned `household_calendar_event` resource,
not a reinterpretation of legacy shared local events or personal Google links.
It is HOME-only and appears in the existing combined calendar as source
`household`. Existing local/Google contracts and sync workers stay unchanged.

- API base: `/v1/calendar/household-events`; authenticated GET list, POST create,
  PUT `/{id}` update, DELETE `/{id}?revision=N`, and GET `/members` returning only
  active eligible household account IDs/usernames, not emails, roles or secrets.
- Create: title, optional description, startsAt/endsAt instants, timeZone and
  participantIds (up to 50, unique). Core always includes the creator and rejects
  disabled, foreign or calendar-read-ineligible participants. No provider target
  or external-write field is accepted.
- Update: title, description, startsAt, endsAt, timeZone and mandatory nonnegative
  integer revision. Participants are fixed for this slice; no participant mutation
  route or silent reassignment is provided. Participant-list management is later
  work with explicit removal/copy-retention decisions.
- Read: household calendar read permission and active HOME membership. Events are
  household-visible; participation controls editing, not a private visibility ACL.
  Returns participantIds, createdBy, revision and server-derived canEdit/canDelete.
- Edit: active selected participant plus calendar:update permission. Creator is
  a participant. Owner/admin status alone does not override participation.
- Delete: conservative first-slice policy is creator-only plus calendar:delete,
  required revision and existing UI confirmation. Joint editing does not authorize
  destructive deletion by another participant. Creator deactivation does not
  prevent remaining eligible participants editing; no owner recovery bypass is
  added. There are no remote copies to delete in this slice.
- All mutations serialize through existing workspace authorization locks and the
  event row, use optimistic revision checks, and audit actor/Space/event/correlation
  atomically. Conflict is HTTP409 `HOUSEHOLD_CALENDAR_CONFLICT`; bad input is
  HTTP400 `HOUSEHOLD_CALENDAR_INVALID`; foreign/missing event HTTP404
  `HOUSEHOLD_CALENDAR_NOT_FOUND`; authorization uses existing HTTP403 `FORBIDDEN`.
- GET accepts a bounded start/end range; oversized result ranges fail explicitly
  rather than silently hiding additional events. Participant filters in Web are
  display-only and never authorize access.

Additive migration V43 is reserved for these new tables and ownership FKs. V42
belongs to the concurrent Gateway assignment. No V1-V42 changes, no new role
grants, no live migration and no runtime replacement occur in this source slice.

## Design questions still open

These remain separate decisions; manual writes are bounded by
[ADR 0038](adr/0038-selected-household-calendar-delivery.md):

- May every participant delete a joint event, or does deletion need a different
  role/confirmation? Joint edit consent alone does not answer destructive deletion.
- What happens to a removed participant's previously delivered provider copy?
  What happens when its creator leaves the household? Native deletion now requires
  explicit retention of existing/uncertain external copies, without remote deletion.
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

Implementation slices add new source migrations; this plan itself never applies
them to a running installation. Never edit
V1-V41 or migrate the running V39 Windows database implicitly. Existing Pi V41
and Windows V39 are separate runtime targets, each needing deliberate deployment.
