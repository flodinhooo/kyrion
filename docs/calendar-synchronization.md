# Calendar synchronization

The [Home family calendar plan](home-family-calendar-plan.md) separates native
joint events, personal read disclosure and explicit selected-recipient delivery.
Each source slice has its own consent boundary and deployment evidence. The
[native results](agent-handoffs/2026-11-06-home-calendar-results.md),
[read-disclosure results](agent-handoffs/2026-11-06-personal-calendar-disclosure-results.md)
and [delivery results](agent-handoffs/2026-11-06-household-calendar-delivery-results.md)
record them separately. Personal Google credentials remain server-side.

The 2026-11-09 source update adds selected personal-calendar read recipients as
[ADR 0044](adr/0044-selected-personal-calendar-recipients.md) specifies. V47 and
the corresponding Core artifact require a separately approved operator rollout.
The Web interface distinguishes disclosure to selected people from receiving
manual shared-event copies into one's own Google calendar. Existing runtime
sharing continues under its installed contract until activation; an older Core
cannot accept new selected-recipient sharing through the updated interface.

## Native joint household events

`/v1/calendar/household-events` is a separate HOME-only resource. New events carry
explicit participants including their creator. With calendar update permission,
either selected partner can edit the canonical event; other household members
with calendar read permission can view it but cannot edit merely because they
are OWNER. The creator alone may delete with delete permission, matching revision
and Web confirmation. Participant lists are fixed in this initial slice.

The existing Web calendar combines `local`, `google` and `household` sources.
Confirmed owned Google copies are conservatively merged with a present native
event as [ADR 0039](adr/0039-owned-calendar-copy-presentation.md) describes. Core
`GET /v1/calendar/household-copy-links` returns only the acting credential owner's
current confirmed links for an actual selected calendar, with optional bounded
start/end. Web also checks identity/private marker, ETag, revision, content and
exact instants; linkage is not returned in the combined browser payload. Changed,
revoked, uncertain, independent or unverifiable copies remain visible. If optional
link lookup fails, both representations remain and Web explains possible copies.
Other members' private/availability projections are not expanded with correlations.

Shared-event creation offers an explicit participant list and an everyone shortcut;
the person filter changes only display. Saving a native event never writes a
personal calendar. Separate manual delivery requires a voluntary destination grant
and explicit recipient selection/confirmation as described below. Calendar role permissions
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
Unchanged existing fields preserve their original absolute instants, seconds and
precision, including the second occurrence of an autumn clock-change hour. Newly
entered nonexistent spring times are rejected with localized feedback instead of
silently shifted. End ordering is validated against absolute instants in Core,
not a misleading datetime-local minimum across a repeated hour. Explicit choice
between both occurrences of a newly authored ambiguous time remains later work.
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

### Manual delivery of native household events (HOME-04)

This is separate from legacy local-event synchronization below and personal read
disclosure above. It follows [ADR 0038](adr/0038-selected-household-calendar-delivery.md).
In Calendar, expand **Receive shared events in my Google calendar**, select one
actual writable calendar and explicitly enable/save the destination. This permits
eligible participants to publish only joint events in which the credential owner
is also a participant. The destination owner needs calendar read/create/update;
an editor needs read/update. HOME membership must remain active. No destination
is opted in by migration, and OWNER cannot configure another account's destination.

Save a shared event first, then reopen it and select recipients under **Send saved
event to selected calendars**. Missing destinations are visible. Confirm sending.
Web makes one explicit Core request per selected destination, in sequence, and
shows each result. It never sends unsaved form changes or automatically publishes
on creation, local edit, refresh, polling or startup. Closing a view stops requests
not yet sent; an already accepted HTTP request may still finish. On an interrupted
response, refresh statuses before retrying. Calendar edits and per-target delivery
are separate operations, so one recipient's failure does not undo another's copy.

- `GET/PUT /v1/calendar/household-destination`: own current setting. PUT requires
  exactly `{calendarId: string|null, revision: nonnegative integer}`. Null revokes
  without provider contact. Positive consent validates the actual current writable
  calendar; aliases such as `primary` are not accepted. Same unchanged active
  destination is idempotent. Revoke/re-enable rotates the grant but reuses an
  existing copy for the same concrete connection/calendar pair.
- `GET /v1/calendar/household-events/{id}/deliveries`: participant-editor-only
  saved revision, current recipient usernames/opaque target IDs and prior statuses.
- `POST` on that path requires exactly `{targetId: UUID, revision: integer}`.
  Core authorizes/reserves one attempt and performs its provider work outside DB
  transactions. Each provider operation and token-refresh retry rechecks the actual
  actor, participant, recipient role/Space, consent, connection, revision and lease.
  A five-minute lease and per-attempt fencing token block concurrent attempts and
  superseded finalization. Expired work is never automatically resumed.
- Result states: `RUNNING`, `SYNCED`, `OUTDATED` (derived from a newer native
  revision), `ERROR`, `CONFLICT`, `BLOCKED`, `NEEDS_REVIEW`. Only a verified matching
  provider copy records the delivered revision. Revocation/change during a write
  cannot recall that HTTP call; it never reports the changed authority as success.
  A missing/disabled destination does not silently redirect to another calendar.
- Stable provider IDs/markers and stored ETags prevent duplicate inserts and blind
  overwrites. A matching desired remote copy can recover a lost create/PATCH
  response without another write. Foreign markers, divergent external changes,
  converted recurrence/all-day events and missing confirmed copies are conflicts.
  A missing copy after an uncertain first insert requires review, not recreation.
  Definitive provider denials preserve a safe manual retry; rate limits are not
  automatically retried. No remote-to-native merge is performed.
- Deleting a native event remains creator-only and revisioned. Live delivery leases
  block deletion. If tracking exists, Core requires `retainExternalCopies=true`
  and Web explicitly confirms that all existing/uncertain personal copies remain
  independent and receive no further updates. Retained-copy audit is atomic with
  deleting local tracking. No external DELETE is called by this feature.

V45 contains only new destination-generation and delivery tables with account,
Space, connection and grant constraints. Destination changes/revocation preserve
old copy history; disconnect nulls the old connection, and a new connection needs
fresh consent. Browser delivery responses contain no provider IDs, ETags or
credentials and use no-store. Core audits configuring credential owner, actual
publishing editor, attempt/copy and correlation without event content or tokens.

`CALENDAR_DELIVERY_INVALID` is 400; unavailable/private/foreign targets use
`CALENDAR_DELIVERY_UNAVAILABLE` (404), stale revisions use
`CALENDAR_DELIVERY_STALE` (409), concurrent attempts use `CALENDAR_DELIVERY_BUSY`
(409), and native deletion without retention acknowledgement uses
`CALENDAR_DELIVERY_RETENTION_REQUIRED` (409). Provider/conflict/revocation outcomes
are persisted per target with stable codes, rather than replacing partial failure
with a blanket success. Existing RBAC denials remain 403.

This first slice is manual Google delivery of timed native events. Remote-copy
deletion, participant changes, provider-to-native reconciliation, automatic delivery,
additional providers and wider private-overlay presentation remain separate work.
Confirmed owned-copy suppression is described above. No live provider write or
rollout is implied. A V45 original-data restore /
upgrade rehearsal is still required; the Gateway migration rehearsal through V43
does not certify it. Older Core binaries do not enforce the new destination or
retention policies: an in-place binary downgrade is not an accepted rollback.

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
