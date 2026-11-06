# Gateway authority results (Assignment B)

Status: bounded Assignment B source slice implemented, fully verified and
committed on `master`. Physical/release acceptance remains separate.
Starting checkout: clean `master` at `fe5e65a`. All work stays in the primary
checkout. No branches, worktrees, resets, stashes, pushes or foreign staging.

## Architecture and resulting behavior

[ADR 0036](../adr/0036-gateway-command-authority.md) was written before
implementation after reading AGENTS, README, the complete ownership handoff,
Gateway architecture, RBAC, Spaces hardening evidence and actual callers.
Both ADR 0036 and migration V42 were unused before creation. Assignment A's V43
remains separate and was included in combined source verification.

- Every Gateway enqueue/await/confirmed-execution call now requires typed,
  explicit Core provenance. Principal, resource Space, permission, capability,
  correlation and applicable target/grant/session/node identities survive queuing.
  No owner default or ambient request identity establishes queued authority.
- Atomic claim checks current human membership/eligibility, enabled state, Space,
  RBAC, target identity, node observation and catalog capability before releasing
  a payload. Denial produces terminal failure and correlated audit, with zero
  dispatch. Removing and recreating a connection at the same address cannot
  inherit a queued command. Suspended Spaces cannot poll; pending rows remain
  pending until reactivation or operator disposition.
- Binding save requires current `devices:update` and `devices:execute`, and issues
  fresh, configurator-attributed grants bounded to button, source node, gesture,
  device/room and power action. Replacement (even identical), deletion, moved
  room targets and configurator permission withdrawal invalidate queued work.
  Grant issuance/revocation audit identifies configurator, Space, button and grant.
- Action entry, idempotency replay, each target and queue release revalidate
  non-human authority. This also protects direct Nanoleaf automation targets.
  Human/Voice historical request hashes remain compatible; automation hashes
  additionally bind grant/node and cannot reuse another grant's cached success.
- HOME Voice uses the distinct satellite plus active unexpired session authority,
  never an inferred human. Business Voice remains blocked. Human accepted intent
  is durable across logout, but not current permission/account/Space revocation;
  revoked HTTP sessions cannot enqueue new intent.
- V42 adds nullable provenance and binding-grant columns, index and consistency
  check. It rewrites no migration, completed/running command or historical audit.
  Legacy pending rows fail closed on claim (`AUTHORITY_PROVENANCE_MISSING`);
  historical bindings stay inactive until explicitly resaved. No grant is
  retroactively attributed to an owner.

[Gateway command authority](../gateway-command-authority.md) contains the full
caller matrix and compatibility/execution limits. Reviewed production paths:
DeviceCommand sync/async; Web Actions and interpretation; HOME Voice;
button workers; direct Gateway pairing/power/brightness/colour; Zigbee approval
and Hue recovery; Bluetooth discovery/approval; Zigbee removal; room removal;
YouTube playback; authenticated claims/results. Observation-only paths do not
create action authority. Existing confirmation/policy, ownership predicates,
bounded adapter contracts and conservative timeout/result handling remain.

## Files and shared coordination

B owns the changed Action contracts/endpoint/orchestrator, DeviceCommand,
ZigbeeButtonBinding, Gateway command/controller/Zigbee approval and the new
GatewayAuthority service; RoomController removal and YouTube playback callers;
V42; focused Action/automation/device tests; the dedicated
`security/GatewayAuthorityIntegrationTest.kt`; ADR 0036 and the two B documents.
The implementation commit's exact path list is recorded below.

No changes to RBAC, TenantBoundary, authentication implementation, route
interceptor, shared build configuration, Voice implementation, AI orchestration,
README, root AGENTS or shared status/TODO were made by B. Assignment A applied the two coordinated
shared `AuthenticationPersistenceIntegrationTest` mock/verify adaptations:

```diff
- commands.execute(owner.id, firstRequest, action.correlationId, false)
+ commands.execute(dev.kyrion.core.gateway.GatewayAuthority.action(action, firstRequest.capability), firstRequest, action.correlationId, false)
```

After review, A explicitly transferred ownership of these exact two call-site
adaptations to B so the signature-changing commit remains independently
compilable. B staged that file only after A separately committed its coordinated
fixture corrections and the remaining diff was exactly those two adaptations. No other shared-test changes are included in B's commit. The initial
compileTestKotlin failure identified precisely these two old-signature calls;
no compatibility overload was introduced to bypass authority. Coordination uses
ignored `gateway-B-status.txt` / `home-A-status.txt` files and exclusive open
.NET FileStreams (`FileShare.None`) on the agreed Git/Core lock files. Lock files
are not deleted. Git index/ref operations and complete Core runs use separate,
non-nested exclusive windows.

## Verification evidence

Final acceptance: **370 tests, zero failures/errors/skips**, and **bootJar
successful**. B executed `gradlew.bat test bootJar --console=plain` under the
exclusive Core lock: BUILD SUCCESSFUL in 2m 22s. This includes GatewayAuthority27,
HouseholdCalendar10, shared AuthenticationPersistence88, WebActionService5 and
all other Core suites. No tests were skipped or quarantined. JDK 21 is the
existing ignored local toolchain.

Tested base HEAD was `9599f34ddf4e02df519a438e391c7a8cc1ec55e7`, plus the explicit
B changes and A's frozen Calendar/V43 source. SHA256 manifests over every Core
source/resource/test file and build/settings configuration were identical before
and after the run, and were checked again after B's implementation commit.
Manifest digest (sorted path/hash map):
`ee14d8428c81ddecd9dd30b80e10e2408439adf485f0d3b59f4649ed72e407bc`.
Final log: `.run/gateway-authority-full-final.log`; manifests:
`.run/dev-recovery/coordination/gateway-final-before.json` and
`gateway-final-after.json`; XML: `services/core/build/test-results/test/`;
local aggregate: `.run/gateway-authority-final-test-summary.json`.

The following intermediate evidence is retained for traceability, not used as
failed-run acceptance:

- B focused command: `gradlew.bat test --tests '*GatewayAuthorityIntegrationTest'
  --tests '*gateway.*' --tests '*action.*' --tests '*ZigbeeButtonBindingTest'
  --tests '*DeviceCommandServiceTest' --console=plain`: **48 passed**, zero
  failures/errors/skips before the final additive regressions; log
  `.run/gateway-authority-focused-retry.log`.
- First combined full run by A: 368 tests, all 26 Gateway cases passed; 10 new
  Calendar fixture failures. Source hashes stable. These are not final acceptance.
- Next B-run `test bootJar`: 369 tests, all 26 Gateway cases and 5 WebActionService
  cases passed; one remaining Calendar HTTP failure. Core source hashes unchanged
  (`gateway-before-calendar-fix-before.json` /
  `gateway-before-calendar-fix-after.json`); log
  `.run/gateway-authority-full-before-calendar-fix.log`. A owns that correction.
- Gateway tests exercise real PostgreSQL/Flyway, HTTP authentication and current
  production services. Coverage includes member provenance; role revocation
  between enqueue/claim; disabled/missing/foreign principals; suspended Space;
  removed/recreated target and removed capability; cross-node/Space claims and
  results; missing historical provenance; grant deletion/identical resave,
  configurator revocation, source/target/action/capability scope and room movement;
  HOME/Business Voice session boundaries; synthetic Action-to-queue-to-confirmed
  completion and denied cached replay; retained retry identity; concurrent and
  duplicate claims/results; correlated denial and grant lifecycle audit.
- The V41-to-V42 isolated upgrade regression retains old command payload/status/
  correlation, binding configuration and previous migration checksums, and asserts
  that neither command authority nor automation grants are manufactured.
- Full-suite existing between-target human permission-revocation tests retain
  their behavior through the coordinated explicit-authority signature adjustment.
- `bootJar` and Kotlin compilation succeeded. Configured tasks/build scripts were
  inspected: no dedicated Core formatter, linter or separate type-check task is
  configured. Kotlin/Java compilation and full `test`/`bootJar` are the available
  Core checks. No dependency or build configuration was added.

Intermediate failures are excluded from acceptance: an expiry test initially
used DB-now minus one second against the Core clock (fixed to an unambiguous past
instant); a retry encountered Testcontainers PostgreSQL startup timeout (fresh
isolated retry passed); Calendar bootstrap/Instant-input failures are owned and
corrected by A. Existing JVM class-sharing/Gradle notices are non-failing.

## Delivery and remaining limits

Shared fixture coordination is resolved: A reviewed the four explicit-past
expiry/due assignments, verified the three affected historical tests, and
committed only those fixture hunks as `84c04fc`. A then aligned two mail cooldown
fixtures to application `Instant.now()-61s` (preserving current-hour accounting)
and the remaining email/domain expiry fixtures to an explicit past instant;
focused mail/DNS tests passed before the separate fixture commit `9599f34`. Production code and all existing
assertions remain unchanged. B's separately transferred shared-test diff is
exactly the two GatewayAuthority call-site adaptations. The full 370-test run
before that fixture correction passed Gateway27/Household10/WebActionService5
but had three historical fixture failures; its log is preserved as
`.run/gateway-authority-full-before-fixture-fix.log`. The subsequent single mail
cooldown fixture failure is retained in `.run/gateway-authority-full-before-mail-fix.log`;
A's second focused fixture check and `9599f34` resolved it before the final green run.
No persistent host/container
clock offset is asserted; the correction removes the cross-clock one-second
fixture assumption.

Commits:

- `c398402acab08ca1fc45b15be6268f3599c7da87`: B authority implementation, ADR 0036,
  V42, caller adaptation and focused regressions; exactly the 21 explicit paths
  listed below, with no Calendar/V43/Web or private files.
- `84c04fc` and `9599f34`: A-owned prerequisite test-fixture corrections, already
  on `master` before B's final full verification; no product-security changes.
- This results document is delivered in a separate documentation commit. Its
  exact ID is available through `git log -1 --
  docs/agent-handoffs/2026-11-06-gateway-authority-results.md` and the final chat
  response, avoiding a self-referential commit hash in this file.

Git mutations held the exclusive Git lock, checked an empty index before
staging, staged explicit filenames only, verified the complete staged path set
and `git diff --cached --check`, then committed. Final own `git diff --check`
passed. No foreign staged changes were adopted. A's Calendar work remains
separately owned; its staged/committed publication does not change the tested
Core source manifest. There are no remaining shared-source changes required
for B's bounded slice.

No deployment, production migration, runtime restart, gateway/device action,
provider-account operation or paid request was performed. PostgreSQL migrations
ran only in disposable test databases/schemas. All physical completions in new
tests are synthetic; this does not establish radio, audio, satellite or device
acceptance. SingleSpaceRuntimeGuard remains unchanged.

Revocation cannot recall a physical operation already released to an adapter.
No automatic replay of uncertain running commands is introduced; future retries
must retain and revalidate original provenance. Historical bindings need explicit
resave before operating. An older Core binary that omits authority validation is
not a security-preserving rollback merely because V42 is additive. Deployment,
physical acceptance and broader multi-process/device reconciliation remain
separate release work.

## Exact B implementation paths

The results document itself is committed separately. The implementation stages
only these 21 explicit paths (including the coordinated two-line shared test
adaptation):

```text
docs/adr/0036-gateway-command-authority.md
docs/gateway-command-authority.md
services/core/src/main/kotlin/dev/kyrion/core/action/ActionContracts.kt
services/core/src/main/kotlin/dev/kyrion/core/action/ActionEndpoint.kt
services/core/src/main/kotlin/dev/kyrion/core/action/ActionOrchestrator.kt
services/core/src/main/kotlin/dev/kyrion/core/automation/ZigbeeButtonBinding.kt
services/core/src/main/kotlin/dev/kyrion/core/capability/DeviceCommand.kt
services/core/src/main/kotlin/dev/kyrion/core/gateway/GatewayAuthority.kt
services/core/src/main/kotlin/dev/kyrion/core/gateway/GatewayCommand.kt
services/core/src/main/kotlin/dev/kyrion/core/gateway/GatewayController.kt
services/core/src/main/kotlin/dev/kyrion/core/gateway/ZigbeeIntegration.kt
services/core/src/main/kotlin/dev/kyrion/core/home/RoomController.kt
services/core/src/main/kotlin/dev/kyrion/core/integration/YouTubeIntegrationController.kt
services/core/src/main/resources/db/migration/V42__gateway_command_authority.sql
services/core/src/test/kotlin/dev/kyrion/core/action/DeviceActionHandlerTest.kt
services/core/src/test/kotlin/dev/kyrion/core/action/WebActionIntentServiceTest.kt
services/core/src/test/kotlin/dev/kyrion/core/action/WebActionServiceTest.kt
services/core/src/test/kotlin/dev/kyrion/core/automation/ZigbeeButtonBindingTest.kt
services/core/src/test/kotlin/dev/kyrion/core/capability/DeviceCommandServiceTest.kt
services/core/src/test/kotlin/dev/kyrion/core/security/GatewayAuthorityIntegrationTest.kt
services/core/src/test/kotlin/dev/kyrion/core/security/AuthenticationPersistenceIntegrationTest.kt
```
