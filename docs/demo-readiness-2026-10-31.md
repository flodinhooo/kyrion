# October 31 demo checklist

Status: partial readiness. The local UI, local Calendar, HA refresh, Google
provider CRUD/readback and speech APIs were exercised. Google works after the
user's reauthorization; do not request new consent without an actual provider
failure. The approved Pi-to-Windows Core repair and synthetic Voice turn now
pass; see [Sprint 04](status/2026-10-30-stabilization-sprint-04.md). Physical audio,
Gateway target verification and IPv6-first client delays remain open. LAN access
is process-scoped; an ordinary later Core start safely falls back to loopback.

## Preflight

From the existing checkout, with Docker Desktop already running:

```powershell
node infrastructure/dev-stack.mjs status
node infrastructure/dev-stack.mjs start
node infrastructure/dev-stack.mjs diagnose
node infrastructure/demo-smoke.mjs
```

`start` preserves existing services. The public smoke validates readiness and
unauthenticated access denial; it does not establish signed-in feature readiness.
`diagnose` saves sanitized metadata under `.run/dev-recovery/diagnostics/`.
Use `node infrastructure/dev-soak.mjs 30` for a 30-minute observation before the
demo; it never restarts services and retains transient failures in its result.

## Signed-in checks

```powershell
node infrastructure/demo-smoke.mjs --interactive --refresh-ha --local-calendar
# Later runs may reuse only the dedicated profile created by this workflow:
node infrastructure/demo-smoke.mjs --browser
# Explicit live Google CRUD, only its newly marked test event:
node infrastructure/demo-smoke.mjs --browser --google-calendar
```

The browser uses the existing `@playwright/test` installation from `apps/website`;
no new runtime dependency is required. Sign in normally in the opened browser.
Credentials stay in its dedicated ignored profile below `.run/dev-recovery/`;
the smoke does not inspect unrelated session caches or export cookies to logs.

Default browser checks only navigate/read. `--refresh-ha` explicitly imports a
read-only HA snapshot and observes periodic refresh without triggering device
overview reads. A manual import resets the 30-second throttle; an intervening
scheduler tick may be skipped, so observation spans two ticks plus a bounded
request allowance. `--local-calendar` creates one clearly marked, local-only
`[KYRION-DEMO-SMOKE ...]` event, verifies edit, timezone and stale-revision rejection,
then checks its exact marker/scope before deleting only that new event.
`--google-calendar` separately opts into creating/editing/removing one uniquely
marked Google test event with conditional ETags and verified cleanup. It never
invokes actor-wide synchronization. No physical device action is performed.

The browser smoke exits nonzero for any failed check. HTTP 200 with
`reauthorizationRequired` or an offline/unconfigured integration is not a
successful integration check. The latest Google run passed all checks.

## Demonstration sequence

1. Login and Dashboard: show actual current status. Keep Recovery reachable.
2. Home, Rooms and Devices: show actual inventory and timestamps. HA is read-only.
   Demonstrate a physical control only after selecting an authorized test device.
3. Calendar: show local and Google operation. Do not modify personal appointments
   to populate the demo; use only explicitly marked test objects.
4. Integrations and System services: distinguish configured, connected, healthy
   and physically verified. Live Google CRUD/readback is verified; more-than-100
   event pagination and external Samsung edits have separate acceptance scope.
5. Lounge: show the actual Spotify device list. Playback and audible output need
   their own authorized physical acceptance; a connected receiver is insufficient.
6. Chat and existing Velora: validate the selected local profile after the parallel
   AI work is frozen. Page rendering is verified; conversational/device execution
   and microphone-to-speaker acceptance are separate gates.

## Recovery and shutdown boundaries

```powershell
node infrastructure/dev-stack.mjs logs core
node infrastructure/dev-stack.mjs logs tts
# Explicit controlled database restart; briefly interrupts Core database access:
node infrastructure/dev-stack.mjs restart postgres --confirm
# Source support in helper v5, after its next coordinated safe launch:
node infrastructure/dev-stack.mjs restart core --confirm
```

Scoped Windows restarts support `core`, `ai` and `ollama`, only when managed by
that helper. They never restart another service or Pi unit; external processes
are preserved with an explicit diagnostic. An older running helper reports
`HELPER_UPGRADE_REQUIRED`. Do not terminate it solely to activate these controls
while shared WSL speech sessions are active. WSL service restart and automatic
global recovery remain excluded. PostgreSQL restart preserves the existing
container/data and waits for SQL plus an already-running Core to reconnect.

For a full stop, stop foreground Web/AI/Core in their owning terminals, then stop
PostgreSQL with `docker compose -f infrastructure/compose.yml stop postgres`.
Coordinate speech shutdown with the other operator. Do not use `down -v`, reset
database history, terminate global WSL/Docker or restart Windows during the demo.
A full Windows reboot requires explicit approval and a coordinated restart test.

The Pi resolves `kyrion-core.home` to the Windows LAN address but could not
connect to port 8080 during verification. Core defaults to loopback and the shared
configuration had no explicit bind override; the existing Windows firewall rule
allows the two reserved Pi addresses. A coordinated Core launch with an explicit
`KYRION_CORE_ADDRESS` suitable for that trusted LAN, followed by a Pi connectivity
test, is required before Voice can be claimed. Do not weaken the firewall or
repoint the Pi blindly. The running Core and parallel AI work were preserved.

See [Sprint 02 evidence](status/2026-10-30-stabilization-sprint-02.md).
For the later Google acceptance and reviewed LAN repair, use
[Sprint 03 evidence](status/2026-10-30-stabilization-sprint-03.md) and the
[Pi/Core and Voice procedure](pi-core-and-voice-acceptance.md).
