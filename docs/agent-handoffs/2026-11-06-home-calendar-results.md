# Home calendar results (Assignment A)

Status: native household-event source implemented and automatically verified.
No runtime deployment or live provider acceptance.
Baseline: `fe5e65a` on master, concurrent Gateway Assignment B.

## Implemented native slice

The native household-event slice follows HOME-01 in the
[plan](../home-family-calendar-plan.md). New events have one Core identity,
explicit participants including the creator, mandatory update/delete revisions
and creator-only deletion. Eligible participants jointly edit content, without
granting each other personal Google access. Legacy local events and provider
sync code are unchanged. No participant-list mutation or external delivery is
provided in this slice.

V43 adds dedicated event/participant tables with composite Space/account foreign
keys. V42 is owned by B and was not changed. Core reuses existing calendar
permissions and workspace mutation locking, retains the HOME/single-Space
boundaries, and records actor/Space/event/correlation with transactional audit.
The existing Calendar view adds shared creation, participant selection, display
filtering, shared event editing, explicit conflict feedback and DE/EN resources.
The combined read keeps legacy/Google events available when shared-event support
is unavailable; it reports this state rather than claiming an empty success.

## Shared coordination

B requested two call-site adaptations in
`AuthenticationPersistenceIntegrationTest.kt` for its explicit GatewayAuthority
signature. A applied those exact changes and explicitly transferred staging of
only those two adaptations to B's signature-changing source commit; no B
implementation file is staged by A. A paused Core source edits for B's
focused/full verification window and is validating Web independently. Ignored
status files live in `.run/dev-recovery/coordination/`; the exclusive build/Git
FileStream locks remain authoritative.

## Current verification

- Focused Calendar/Web route and model tests: 32 passed.
- Full Web unit suite: 211 passed; ESLint, TypeScript and isolated production
  build passed. Next's generated build-directory tsconfig additions were removed.
- Household Core integration suite: all 10 tests passed, including actual HTTP
  creation/editing, concurrent edits, transactional audit rollback, revocation,
  foreign Space denial, invalid input and legacy preservation. The final combined
  Core suite passed **370 tests**, zero failures/errors/skips, and `bootJar` passed.
  The run includes all 27 Gateway integration cases; its recorded before/after
  Core source hashes match. No claim of live database migration or real
  user/browser acceptance follows from source tests.
- The request parser explicitly deserializes ISO Instants using existing Jackson
  databind; Spring's Jackson 3 response support does not provide a Jackson 2
  request time module. No dependency or permissive coercion was added.
- Early failures were corrected rather than skipped: A's test bootstrap fixture
  now uses a real test-only SessionTokenService token; the valid HTTP request
  uncovered the missing Instant conversion. Subsequent combined runs exposed
  narrow database-clock-relative expiry/cooldown fixtures in the existing shared
  authentication suite. A corrected only those test timestamps, retaining all
  expiry, cooldown, replay, scheduling and security assertions. The initial four
  fixture-only hunks were committed separately in `84c04fc`; the remaining mail/
  domain fixture corrections in `9599f34`. Rate-limit resend
  timestamps stay within the hour using the application clock. No persistent
  host/DB clock fault is asserted and production time logic is unchanged.
- No deployment, live migration, service restart, provider write, account reset
  or real device action has been performed.
- The final combined run used starting HEAD `9599f34` plus the frozen A/B changes;
  evidence is `.run/gateway-authority-full-final.log` and the private ignored
  `coordination/gateway-final-before.json` / `gateway-final-after.json` manifests.
  Verification of that combined working tree is distinct from attribution to
  either chat's later source commit. `git diff --check` passed. Core has no
  separately configured formatter/linter task; existing deprecation warnings
  remain non-failing. No new dependencies were introduced.

## Source integration

Gateway source and its two coordinated shared test call sites are committed in
`c398402`; A's fixture prerequisites are `84c04fc` and `9599f34`. A's feature
commit contains only Calendar/V43/Web and its coordinating documentation; find
its exact ID with `git log -1 -- services/core/src/main/kotlin/dev/kyrion/core/calendar/HouseholdCalendar.kt`.
The primary checkout remains on master. No branch/worktree, push or runtime
replacement is part of this delivery.

Remaining HOME-03/04 personal calendar grants/provider deliveries, participant
management, multi-HOME identity and cross-installation login remain planned.
No AI-context or satellite retrieval of this new resource was added implicitly.
