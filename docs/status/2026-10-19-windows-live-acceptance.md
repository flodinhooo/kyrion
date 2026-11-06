# Windows local integration recovery and live acceptance

Status: updated local stack running; HA provider-to-persistence acceptance passed;
authenticated browser and Google account-holder acceptance remain open. This is
not a claim of complete live bidirectional Google acceptance.

## Environment and versions actually inspected

- Windows PC. Main checkout: `refresh/product-credibility` at `5c000c6` when
  inspected. Recovery worktree: `.worktrees/calendar-ha-recovery`, branch
  `fix/calendar-ha-recovery`, based on `547f0ae` with uncommitted recovery changes.
- Initially, Web on port 3000 served the main checkout, while Core on loopback
  8080 ran the October 11 JAR with Java 22. The previous fixes were not running.
- After checking clean Web/Core source in the main checkout, zero active actions
  and database activity, only those identified local app processes were replaced.
  Existing Web sessions were not reset. Current Web serves the recovery worktree
  on `http://localhost:3000`; Core runs a frozen copy of its updated JAR with Java
  21 on `127.0.0.1:8080`. Core health reports `UP`.
- Final observed Core PID: 39208; Web listening PID: 15100. The launch manifest
  under `%TEMP%\kyrion-recovery-development\launch-20261019-174303.json` records
  source/configuration roots and artifact SHA-256
  `B592336BACFD047DEDF8536D07973626B1F7A465C64B4FF8BB0D70915EB577F9`.
- Docker Desktop was running. `kyrion-postgres` exposes PostgreSQL 17 on loopback
  5432 using the existing E: data mount. The unrelated database on 5433 was not
  touched. AI on 8000 and the other development runtimes were not replaced.
- Existing configuration is loaded from the primary checkout without copying or
  overwriting `.env` files. Credential keys and tokens were never printed.
  The Google callback is `http://localhost:3000/api/integrations/google/callback`.
  Home Assistant is configured at a private LAN address, not localhost.
- No Raspberry Pi deployment, production-service change, branch merge, external
  calendar event write or real device command was performed.

## Confirmed Windows defects and fixes

1. The live database held V31 checksum `1755433543`, while the repository SQL had
   been reformatted to a different checksum. This blocked startup even though the
   SQL semantics were identical. Restored the exact historical SQL from the
   applied artifact and added a checksum regression test. No Flyway repair,
   checksum rewrite or validation bypass was used. Existing installations with
   another V31 history require explicit review before merging/deployment.
2. A worktree has no private `.env` by design. The launcher explicitly imports the
   original Core configuration and preloads the original Web configuration while
   directing Web to the selected Core port.
3. Passing Node `--env-file` into Next dev led to its child process rejecting the
   flag in `NODE_OPTIONS`. A native `.env` preload fixes this observed failure.
   Web startup now checks that the process remains alive and opens its port.
4. Core now runs an immutable JAR copy so rebuilding does not replace resources
   underneath a running JVM. Launch metadata makes the actual source/artifact
   distinguishable from the main checkout.
5. Development and production Web builds use separate output directories. The
   acceptance output is ignored by Git and ESLint, and its generated route types
   are included by TypeScript. The generated build output is not source to lint.

## Calendar findings

The actual local database contains two events, both in September 2026. No October
local events exist. Both records belong to the account assigned OWNER; that role
has the calendar catalog permissions. The records survived migration and no fake
appointments were seeded. An empty October view is therefore consistent with the
stored data. Authenticated September rendering has not yet been inspected.

Google access-token reads returned HTTP 401. A read-only connection diagnostic
attempted token refresh and received HTTP 400 `invalid_grant`. This is a confirmed
authorization failure, not evidence of a rendering defect; the account holder
must reconnect. The exact reason Google invalidated the token was not inferred.
No Google calendar events could be read or written with that credential.

Core also rejects recurring/all-day edits and deletions even through direct API
requests, and excludes media-account metadata from physical device inventory.
The implementation now retains revoked-authorization state in encrypted metadata,
stops repeated failed refresh requests, and exposes a reconnect action even when
a connection already exists. Reconnection does not require deleting the stored
connection first. Fresh provider consent and live calendar discovery still need
the account holder.

Local CRUD, scoped visibility, dates/timezones, conditional export/import,
identity, conflict handling and deletion are verified with fixtures and disposable
PostgreSQL. They were not exercised by inserting events into the live database.

## Automatic synchronization

Added an explicit per-account opt-in with interval 60–86400 seconds. Defaults are
off, including this installation: the final live check found zero schedule rows
and zero mapped pending exports. The agent did not activate it.

Manual and automatic runs reuse the same engine and persistent lease. Failures
persist attempt/retry/error metadata, use exponential backoff and honor numeric
provider Retry-After. HTTP 429 stops the remaining batch and gates manual retries.
Current RBAC is checked; revoked permissions suspend a schedule. Only explicitly
mapped events for that account are eligible. Conflict preservation and recurring/
all-day write restrictions remain. Browser range refresh displays new external
events while an enabled schedule is viewed. Two scheduler threads prevent a slow
Google provider from starving HA refresh; a blocking-task integration test covers
that separation.

## Home Assistant and lights: live evidence

- The configured HA endpoint returned HTTP 200 for the same fixed, read-only
  snapshot template used by Core. It supplied 21 entities for five physical
  devices, all sensor devices. This connection supplies no light entities.
- A temperature sensor reported 25.1 °C during a trace. Its stable provider
  identity mapped to the existing Kyrion record with the same value. Core
  observation timestamps advanced across successive 30-second refreshes. The
  inventory stayed at five physical HA records; the encrypted connection remains
  separate. Four observations were online and one degraded in the sampled run.
- The suspicious 0% battery is actually reported as `"0"` with unit `%` by HA;
  Kyrion did not synthesize it from a missing field. Two devices still had null
  battery readings. Its provider update date is old, independently of the recent
  temperature update and fresh Core fetch.
- The existing device-level `measuredAt` conservatively uses the oldest included
  entity timestamp. That may be weeks old even when temperature changed today.
  Cards now label this as the oldest included provider update and separately show
  the Core observation time. Neither timestamp proves a physical measurement.
- Both existing Nanoleaf lamps accepted read-only state retrieval: one reported
  on/38%, the other off/0%. No control request was sent. The Hue lights belong to
  the separate gateway/Zigbee path, whose stored gateway heartbeat was from
  August 28. No live HA-to-Hue trace is possible when HA exposes no light entity,
  and no gateway was repointed or production service altered to manufacture one.

The live trace establishes provider-to-Core-to-persistence updates. Authenticated
Core/Web responses and final device-card presentation still require login.
Manual-refresh and disconnected/reconnected scenarios passed controlled tests;
the live HA server was not stopped or modified to simulate an outage.

## Browser and test evidence

Playwright opened the real local application, rendered and visually inspected its
login page, and confirmed `/calendar` redirects to `/login` without a session.
The protected calendar API returned HTTP 401. The interactive acceptance browser
was left ready for account-holder login; no session was fabricated and no password
was read. Month/week/day controls, source selection, live CRUD, settings and device
cards are not claimed as visually accepted while authentication is pending.

Final automated checks: 217 Core tests passed, zero failed/skipped, including
PostgreSQL/Flyway upgrade, live-history checksum, persistent scheduling/leases,
rate-limit backoff, permission revocation, and independent scheduler capacity.
Web: 121 tests passed across 43 files. ESLint, TypeScript, generated route types,
Core bootJar and the Web production build passed. The full PowerShell launcher and native Web environment preload were exercised
against the local stack and passed health checks. The launcher also refused
occupied ports without replacing their owners. These results do not substitute for provider acceptance.

## Required acceptance actions and future control

1. Log in in the acceptance browser and navigate to September. Verify the two
   existing events, month/week/day navigation and accurate local times without
   changing them. Inspect Devices and the HA timestamp/value diagnostics.
2. Reconnect Google through `/plugins/google`. Verify calendar discovery, range
   reads, all-day and recurring display. A non-primary calendar should be selected
   explicitly. Keep automatic synchronization off during read-only acceptance.
3. Only after explicit authorization, use a disposable Google calendar and
   purpose-created events for bidirectional creation/update/conflict/deletion and
   retry acceptance. No live write approval was provided in this session.
4. If local CRUD acceptance needs a new event, have the account holder create an
   intentional test appointment. Do not seed live data just to fill an empty view.
5. A fresh Hue trace needs a deliberately configured development gateway or HA
   light entity. Do not repoint a production node without an explicit handoff.

HA control remains planned. A safe extension needs explicitly enrolled, persisted
entity mappings and bounded adapter capabilities, with Core target validation,
RBAC, approval policy, correlated audit and provider-confirmed results through the
existing Action Orchestrator/DeviceCommandService. Do not expose arbitrary HA
services or grant controls merely because an entity is a light.

## Review and startup

Changes remain uncommitted in the isolated worktree; the branch has not been
merged. Review the full diff, especially V31 history and migration compatibility,
then commit only reviewed Core/Web/docs/development files on the recovery branch.
Do not stage the public website or private configuration. Update/rebase onto the
review target without discarding its landing-page changes, rerun affected checks,
and merge only after approval and the acceptance gates above.

[Windows commands and launcher behavior](../windows-development.md) provide
reproducible PowerShell steps, log/manifest locations and safe port checks. The
pre-migration private backup remains outside Git under
`%TEMP%\kyrion-local-acceptance-backups`.
