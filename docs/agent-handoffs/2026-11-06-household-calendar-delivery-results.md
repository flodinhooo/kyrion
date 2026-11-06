# Selected household calendar delivery results

Status: first HOME-04 Google manual-delivery slice implemented and verified; not deployed.
Baseline: master `ce10573`; preceding source slices are native household events
`69cee10`, personal disclosure `1ed89e1` and Gateway rollout fix `157a399`.
Decision: [ADR 0038](../adr/0038-selected-household-calendar-delivery.md).

## Result and boundaries

An account explicitly opts into one writable Google destination, independently of
personal read disclosure. Active selected participants can manually publish a saved
joint native event there with the required editor/recipient permissions. OWNER
cannot consent for someone else. Recipient selection and sending are explicit;
local edits do not automatically write personal calendars. Web sequences one Core
request per selected target and displays individual results and missing grants.

V45 adds immutable consent generations and per-destination copy/attempt state.
Stable copy IDs, markers and conditional ETags support idempotent retries and keep
external edits as conflicts. Revocation, connection change, membership/role changes,
stale native revisions and active attempts are revalidated by Core before provider
operations, including refresh retries, and before successful finalization. HTTP is
outside transactions. Leases and attempt fencing protect concurrent retries.
Ambiguous writes need review; exact matching responses can be recovered without
another write. A definitive denied first insert remains manually retryable.

Native deletion remains creator-only, revisioned and blocked during live delivery.
Existing/uncertain personal copies require explicit retain acknowledgement and
remain independent; local copy tracking is removed with retained-copy audit.
No provider deletion, automatic conflict resolution or background delivery is added.
No provider identifiers, ETags or credentials enter the delivery Web response.

Implementation paths:

- Core: `calendar/HouseholdCalendarDelivery.kt`, `HouseholdDeliveryRepository.kt`,
  `HouseholdDeliveryController.kt`; focused hooks in `HouseholdCalendar.kt` and
  guarded operations in `integration/GoogleIntegration.kt`; additive V45.
- Web: Calendar page, `household-destination.tsx`, `household-deliveries.tsx`,
  typed `delivery-model.ts`, server proxy and authenticated/CSRF-protected routes;
  DE/EN Calendar resources and explicit retained-copy DELETE forwarding.
- Tests: new `HouseholdCalendarDeliveryIntegrationTest.kt` with a fake provider
  behind the real Google credential/refresh/guard path; new Web `delivery.test.ts`.
  No dependency, role grant, applied migration, Gateway or AI change.

## Verification

Initial focused Core: 47 passed, including the first 19 delivery tests, native10,
disclosure13 and Google5. Additional denial/refresh-retry, lost PATCH response,
in-flight edit and actual foreign/Business cases were added before the frozen final
full Core acceptance window. Web225 tests, ESLint and typecheck passed; final
production build passed, including its TypeScript check. Only Next's temporary
build-directory tsconfig includes were removed; no build configuration change is
delivered. Final full Core: **410 tests**, zero failures/errors/skips, `bootJar`
passed in 4m46s. This includes all 24 new delivery cases, Household10,
Disclosure13, Google5, Gateway28 and the isolated migration rehearsal1. Existing
Kotlin/JVM deprecation warnings are non-failing; no separate Core formatter/linter
task is configured.

The exclusive runner recorded unchanged before/after Core source hashes, JDK21
and artifact inventory through V45. Evidence is under ignored
`.run/dev-recovery/gateway-acceptance/cc4804a9378f44a6a56db41934786e61/`;
`evidence.json`, `gradle.log` and source manifests distinguish source verification
from release authorization (`rolloutAuthorized=false`). Focused and Web logs are
under `.run/dev-recovery/coordination/home-delivery-*`. `git diff --check` passed.
The source is integrated on master with explicit owned paths under the Git lock;
find its feature commit through this report's history. No branch or worktree was
created, no files from Chat B were staged, and no push was performed.

## Remaining acceptance

Source work does not deploy or migrate either installation. No real provider call,
calendar write, credential reset, device action or runtime restart was performed.
Windows remains V39 and Pi V41 from the separate read-only inventory. The Gateway
rehearsal targets V43; the source/artifact now contains V45. An approved exact
artifact/catalog, original-key/data V45 upgrade/restore drill and disposable live
provider/browser family acceptance remain open before release.

Further work: duplicate suppression of managed copies in Google overlays,
provider-to-native reconciliation policy, participant removal/copy cleanup,
recurrence/all-day authoring and other providers. Remote-copy deletion is not
inferred from joint-edit consent. Multi-HOME identity remains a separate milestone.
