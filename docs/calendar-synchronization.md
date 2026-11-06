# Calendar synchronization

The [Home family calendar plan](home-family-calendar-plan.md) separates native
joint events from later personal-calendar grants and provider delivery. The first
native slice is implemented and automatically tested; [Assignment A's results](agent-handoffs/2026-11-06-home-calendar-results.md)
record its current evidence and deployment boundary. It does not remove the
personal Google connection restrictions described below.

## Native joint household events

`/v1/calendar/household-events` is a separate HOME-only resource. New events carry
explicit participants including their creator. With calendar update permission,
either selected partner can edit the canonical event; other household members
with calendar read permission can view it but cannot edit merely because they
are OWNER. The creator alone may delete with delete permission, matching revision
and Web confirmation. Participant lists are fixed in this initial slice.

The existing Web calendar combines `local`, `google` and `household` sources.
Shared-event creation offers an explicit participant list and an everyone shortcut;
the person filter changes only the display of these shared events. No native
joint event is written to a personal provider calendar. Those deliveries require
separate voluntary destination grants in HOME-03/04. Calendar role permissions
must already be assigned; this migration does not expand any existing role.
For first use, the owner grants calendar read/create/update/delete operations as
appropriate through the existing Roles UI. A selected read-only member can view
the event but still needs calendar update permission before editing it.

Every mutation revalidates current membership/permission, uses a revision and
records the actual actor and Space atomically with the event. Stale writes fail
with `HOUSEHOLD_CALENDAR_CONFLICT`; a foreign household event is not found.
The separate tables and composite foreign keys are additive V43, following the
concurrent Gateway V42. Legacy local rows, Google mappings and applied migrations
are unchanged. No runtime rollout is implied by this source implementation.

Implemented recovery slice, 2026-10-19. Live provider acceptance is separate from
fixture and database verification. See [ADR 0024](adr/0024-calendar-sync-and-ha-refresh.md).

## Data flow and ownership

The Calendar page uses authenticated same-origin Web routes. These forward the
server session to Core. Core owns workspace-local events, RBAC and audit, and
calls Google with encrypted personal connection credentials. The browser never
receives OAuth credentials. Local events remain shared workspace resources;
Google connections remain personal. Another member cannot change or synchronize
a local event linked to someone else's Google connection.

Local CRUD uses `local_calendar_event` independently of Google. The editor converts
stored instants to browser-local inputs before converting edits back to instants.
Web sends the local revision on edits/deletion; stale revisions produce
`CALENDAR_SYNC_CONFLICT`. Legacy clients may omit the revision.

## Reading external calendars

### Voluntary household disclosure (HOME-03)

The new personal disclosure slice follows [ADR 0037](adr/0037-voluntary-personal-calendar-disclosure.md).
On Calendar, expand **Share my personal calendars**, select Private, Event times
only or Event details for each actual Google calendar, and explicitly save. Sharing
requires confirmation and applies to all current active HOME members with calendar
read permission; it is not a per-recipient grant. No calendar is shared by default.
Only the connecting account may change its settings, with calendar read/update
permissions. OWNER has no override. Positive sharing requires a readable actual
Google calendar ID; the `primary` alias is rejected. Existing roles are unchanged.

Select one **Personal calendar shared with me** to overlay its events on the
combined calendar. Person filtering changes display only. Shared events are always
read-only; joint native event editing remains separate. Availability returns only
opaque IDs and event time boundaries, with a localized Occupied label in Web.
Details additionally returns title/description. No provider IDs, ETags, calendar
names, emails, token or provider marker are exposed in either shared projection.
All-day dates retain their exclusive end date. This event-interval view is not yet
an authoritative free/busy or free-slot suggestion API.

Endpoints are `/v1/calendar/personal-disclosure` (GET own settings, PUT revisioned
change), `/sources` (GET visible sources) and `/sources/{id}/events?start=...&end=...`
(GET redacted range, at most 400 days). Existing own Google endpoints stay personal;
no other-member credential proxy or shared mutation endpoint is added. Invalid
inputs use `CALENDAR_DISCLOSURE_INVALID` (400), stale settings or in-flight changes
use `CALENDAR_DISCLOSURE_CONFLICT` (409), and absent/private/foreign sources use
`CALENDAR_DISCLOSURE_NOT_FOUND` (404). Missing permissions use existing 403 errors.

V44 stores explicit opt-ins bound to the credential owner, Space, actual connection
and calendar, with optimistic revisions and transactional audit. Disconnect deletes
grants through a foreign key; a new connection requires fresh consent. Setting
Private does not contact Google and works during a provider outage. Removing the
source owner's or reader's calendar permission, deactivating accounts or suspending
the Space prevents subsequent access. Re-enabling roles can restore an existing
opt-in; use Private or disconnect to revoke the opt-in itself.

Core checks authorization before HTTP and again afterwards under the existing
workspace mutation lock. A changed grant invalidates the in-flight result. Shared
representations are never persisted/cached. Web clears previous shared data before
refresh and on errors, polls every 30 seconds while visible, and refreshes on focus.
Revocation cannot erase information already read or copied. No AI/Voice context
consumer was added; future consumers must use the same redacted boundary. Further
providers, multiple simultaneous overlays, destination writes and real provider
acceptance remain follow-up work. Source delivery does not imply a runtime rollout.

The direct Web Google event GET forwards `calendarId`, `start` and `end` to Core
without dropping calendar selection or timezone offsets. Only these bounded
filters are forwarded and reads are uncached. Live October 30 acceptance after
the user's reauthorization covered marked event create/edit/readback, stable IDs,
ETag conflict rejection and cleanup; see [Sprint 03 evidence](status/2026-10-30-stabilization-sprint-03.md).

Select a Google calendar in Calendar. Core requests the visible month/week/day
range, follows all pages within a 10,000-event safety bound, and expands recurring
instances through Google's `singleEvents` mechanism. Date-only all-day events
retain their exclusive end date. Cancelled events disappear on the next read.
Local and remote identities remain separate; linked remote copies are filtered
from the combined view. Google errors, disconnected state and empty results are
distinct. Navigation/Refresh fetches current data; it never writes to Google.

Ordinary non-recurring timed Google events can be edited/deleted directly with
their current ETag and selected calendar. Core uses conditional PATCH/DELETE,
preserving fields outside the bounded editor. All-day events and recurring
instances are displayed read-only in this slice.

## Explicit linked synchronization

For a local timed event, select **Synchronize this event with Google**, select a
writable target calendar, save, then choose **Synchronize**. Each opted-in event
persists the acting account, target calendar, deterministic remote ID, provider
ETag, revision and pending/conflict/error status. Nothing exports all local events.
Legacy flags with no target remain `configuration_required` and never export.

`POST /v1/calendar/sync` requires all four calendar permissions and only processes
the acting user's linked events. Inserts use UUID-derived Google-compatible IDs
and a private Kyrion marker. An uncertain insert is recovered only if its marker
and content match; divergent data becomes a conflict. Local changes PATCH only
the expected ETag. Clean linked events accept remote edits on synchronization.
Concurrent local revisions/provider versions cannot be overwritten by a stale
completion. No database transaction spans Google HTTP requests.

Local deletion of a linked event creates a visible pending-deletion tombstone.
Sync deletes the remote event conditionally, and removes the tombstone only after
confirmation (or a confirmed already-missing remote). Temporary errors retain the
operation for a manual retry. Rate limits never cause an automatic write storm.
Remote deletion/cancellation of a retained local event becomes a conflict, keeping
the local copy rather than recreating Google data or destroying local data.

Conflict resolution is deliberately conservative: review Google separately, then
disable synchronization and save to retain a local copy. This also cancels a
pending deletion locally. It never deletes the remote event. Re-enabling against
divergent existing remote content remains a conflict; create a separate new local
event only after deciding which copy to retain.

## Contracts and limits

The Web local-event DELETE route normalizes a successful Core acknowledgement (including an empty HTTP 200) to HTTP 204.
It does not parse successful empty
bodies as JSON. Revision/authentication/permission failures retain their original
status; acknowledgement of a linked event's local deletion does not imply that
its pending remote deletion has already completed.

- Local request: existing title/description/instants/timezone/Boolean intent plus
  optional `googleCalendarId` and `revision`. DELETE accepts optional `revision`.
- Local response adds `syncStatus`, `syncError`, `syncActorId`, `googleEtag`,
  `revision`, `pendingDeletion`, retaining existing IDs and fields.
- Google list accepts `calendarId`, `start`, `end` instants (maximum 400 days).
  Calendar metadata includes `accessRole` and `primary`. Events include ETag,
  cancellation status, description and recurrence identity.
- Google edits require `etag`; Google DELETE requires both `calendarId` and
  `etag`. Unsafe unversioned writes are rejected, rather than silently targeting
  the primary calendar. Existing direct API clients must adopt these parameters.
- Web's combined response is `{items, google: {status, code}}`.
  Sync responds with synchronized/conflict/failure counts and correlation ID.
- Tokens refresh proactively and once on HTTP 401. Revoked authorization reports
  `GOOGLE_REAUTHORIZATION_REQUIRED`. Reconnection identifies the account through
  authenticated Google UserInfo. Switching accounts requires explicit disconnect.
- One Google account per Kyrion account is supported. Calendar writes run on
  explicit manual sync/edit/delete, or an explicitly enabled per-account schedule.
  Existing installations default to scheduling disabled. Scheduling only processes
  already mapped events belonging to that actor, rechecks RBAC and shares a
  persistent lease with manual runs. Interval (60–86400 seconds), last attempt,
  next retry and error state are persisted. Transient failures back off; provider
  rate limits stop the batch and also gate manual retries. Permission revocation
  suspends the schedule. Conflicts are never resolved automatically.
- This is a bounded live range view plus linked-event reconciliation, not a full
  offline Google replica. A global sync token is intentionally not used for this
  range query: Google restricts filters used with sync tokens. A future full
  replica would require per-calendar cursors, tombstones and atomic token commits.
- Recurrence authoring, all-day editing, invitations/attendees, attachments and
  automatic conflict merging remain outside the bounded editor. Imported Google
  events are not silently converted into editable local records.

Protocol references: [Google incremental sync](https://developers.google.com/workspace/calendar/api/guides/sync),
[event updates](https://developers.google.com/workspace/calendar/api/v3/reference/events/update),
[stable event IDs](https://developers.google.com/workspace/calendar/api/guides/create-events),
[OpenID UserInfo](https://developers.google.com/identity/openid-connect/openid-connect).

`GET/PUT /v1/calendar/sync/settings` reads/configures the authenticated account's
schedule. PUT requires calendar update permission, and enabling also requires all
four calendar permissions. Web preserves CSRF and never enables a schedule on
mount. While an enabled calendar is open, the selected range is reloaded at that
interval to display new remote events. Revoked token state is retained inside
encrypted credential metadata; Google can be reconnected without deleting its
connection first. See [ADR 0025](adr/0025-opt-in-calendar-scheduling.md).
