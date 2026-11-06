# Calendar and Home Assistant recovery

Follow-up: [Windows live acceptance](2026-10-19-windows-live-acceptance.md) records
subsequent deployment to the local Windows PC and remaining acceptance gates.

Implementation branch: `fix/calendar-ha-recovery`, isolated under
`.worktrees/calendar-ha-recovery`. Public website files were excluded. Nothing
was deployed; the previously running development stack was not replaced.

## Confirmed causes and evidence boundaries

- Google reads queried only `primary`, future events starting at the current
  instant, and the first 100 results. Month navigation never supplied its date
  range. Past/current-day or other-calendar events could therefore be absent.
- `syncToGoogle` was persisted but had no execution path, remote identity
  reconciliation, conditional writes or retry state. Existing Google CRUD methods
  did not connect that local intent to provider operations. DELETE always used
  `primary`. Only event-list reads retried authentication, ignoring token expiry
  and leaving other operations without refresh.
- Web silently treated optional Google errors as an empty external event list.
  Editing a local event sliced a UTC timestamp directly into `datetime-local`,
  which could shift the saved instant in a different timezone.
- HA was an explicit snapshot importer without scheduled refresh. Device polling
  read persistence while observations expired after 60 seconds; manual general
  device refresh had no HA observer/import path.
- HA connection credentials and physical-device records share a provider, so the
  credential connection could enter inventory/missing-device reconciliation.
- Power presentation checked only `power.set`, although HA advertises
  `power.read`. Light attributes/contact state were not mapped. Connection-level
  failures were not distinguished from physical unknown/never-observed states.
- No real account session or live hardware was used to establish the cause of
  this installation's empty local calendar. Missing local rows, role grants,
  selected dates, OAuth consent and actual HA reachability still require live
  acceptance. Local CRUD and ownership are exercised against disposable PostgreSQL.

## Implementation and synchronization

See [calendar behavior and API contracts](../calendar-synchronization.md),
[HA import behavior](../home-assistant-import.md), and [ADR 0024](../adr/0024-calendar-sync-and-ha-refresh.md).

Calendar changes cover local revision checks, timezone-safe editing, selected
calendar/range pagination, explicit per-event exports, stable remote identity,
ETags, durable pending deletions, conservative conflicts, and manual retry. A
failed clean read remains a read failure; retry cannot export stale local data.
Google account identity comes from authenticated UserInfo and all operations use
the shared token refresh path. Both locales now cover Calendar controls/status.

HA changes reuse its serialized importer on initial/due reads, the 30-second
scheduler and manual refresh. A lock-protected throttle avoids duplicate due
fetches. Read-only light/contact attributes are persisted, missing battery stays
null, and cached readings retain timestamps and explicit failure diagnostics.
The device page rejects late snapshots that would replace newer observations.
Commands still require an existing write capability and Core permission checks.
The scheduler's executor is explicitly excluded from Zigbee command execution
through the existing application-executor qualifier.

## Data safety

V32 only adds columns and marks legacy unmapped sync intent as requiring
configuration. Upgrade fixtures preserve existing local events, device identity,
nullable battery readings, grants and encrypted credential bytes. No reset or
live-data migration was performed. Remote writes run only on user action; all
automated Google tests use mocks. Conflicts retain both sides. Local/Google
account scope, CSRF, RBAC, encrypted credentials and correlated audit remain.

## Validation

Validation uses Core's Gradle/JUnit/PostgreSQL Testcontainers suite and Web's
Vitest, ESLint, generated route types, TypeScript and Next production build.
Final results: 210 Core tests passed (zero failures/skips), 117 Web tests passed
across 41 files, Core `bootJar` passed, Web lint/type checks and production build
passed, and `git diff --check` passed. No runtime dependency was added.
The complete Core HTTP fixture covers local creation, repeated idempotent export,
remote edit import, persisted identity, pending deletion and confirmed removal.
Additional fixtures cover conditional requests, retry/conflict/cancellation,
OAuth refresh/revocation, calendar pagination and all-day/recurring reads. HA
fixtures cover mapping, unknown/unavailable data, units, missing values, identity,
connection diagnostics and recovery/throttling. Existing command-permission and
command-failure tests remain in the full suite.

No browser interaction test or real Google/HA acceptance is claimed. Kotlin has
no repository formatter/linter task; IDE formatting was invoked for the main
changed modules, and `git diff --check` is part of verification.

## Manual acceptance checklist

Use a disposable Google calendar and purpose-created test events for write checks.
Do not use existing personal appointments for destructive tests.

1. With Google disconnected, create/edit a local event in month/week/day views,
   reload, navigate months and check its timezone and persistence. Check denied
   CRUD with a role lacking each required permission.
2. Connect Google, verify account identity, select a secondary calendar and check
   past/current/future, all-day and recurring events. Verify token revocation gives
   a connection error while local appointments remain usable.
3. Opt one test local event into the disposable calendar, synchronize twice, and
   confirm exactly one Google event. Change each side separately and synchronize.
   Change both before sync: expect a conflict and preserved data.
4. Delete only a purpose-created linked test event. Verify pending deletion,
   conditional remote removal and removal after confirmation. Simulate a provider
   outage/rate limit; confirm the pending operation survives and retries safely.
5. Connect HA, open Devices and check names/areas, temperature units, humidity,
   contact/motion, null battery, and read-only Hue power/brightness/color. Repeat
   refresh and verify stable Kyrion IDs without a fake connection device.
6. Change a test device in HA. Check updates on the next due refresh and timestamp
   changes. Temporarily disconnect HA: expect cached readings with integration
   diagnostics, not a false assertion that every physical device is offline.
   Reconnect and verify recovery. Test HA's own unknown/unavailable states separately.
7. For already-supported gateway/Nanoleaf control, verify role denial, failed/pending
   commands and refreshed confirmed state. HA-imported lights must remain read-only.

## Intentional limits

Calendar synchronization is manual and bounded to ordinary timed linked events;
recurrence/all-day authoring, push notifications, a full offline Google replica,
multi-account selection and automatic conflict merging are not implemented.
Range reads use provider pagination, not an incompatible filtered sync token.
Old direct Google edit/delete API clients must supply the new version/calendar
preconditions. HA keeps its existing private-IPv4 snapshot protocol, bounded sensor
set, exact existing-room mapping and read-only authority. It has no WebSocket
subscription or HA control path. These limits are visible rather than represented
as complete provider support.
