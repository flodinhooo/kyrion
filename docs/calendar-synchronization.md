# Calendar synchronization

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
