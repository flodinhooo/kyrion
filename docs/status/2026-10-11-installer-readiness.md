# Installer v1 readiness review

> Update: the source findings R1-R7, the R8 optional-provider failure and the R9
> optional JSON field have since been hardened in code. Consult the
> [security hardening closeout](2026-10-11-security-hardening.md) for current
> implementation, actual tests, migration and remaining release gates. The review
> below is preserved as the pre-hardening evidence; its risk rows and test counts
> are historical and do not override the later closeout.


Date: 2026-10-11. Scope: repository review, isolated automated verification,
test repair, TODO consolidation and implementation planning. No production
deployment, live migration, owner backup operation or physical acceptance.

## Result

Kyrion has an implemented Core/Web/PostgreSQL control plane and developer-operated
Pi deployment. Installer v1 is **not implemented**. The existing migration tools
must not be rerun against the owner's installation. A fresh-install pilot is
blocked by the security and recovery gaps below despite green baseline tests.

The documented YouTube test compilation failure was reproduced and repaired with
Mockito test doubles for the existing GatewayService/GatewayCommandService
constructor parameters. A no-interactions assertion preserves link preparation's
non-execution boundary. That repair changes no production service behaviour or
dependency. A separate new regression exposed a PostgreSQL timestamp-binding
failure in account deactivation; the narrowly scoped production fix is described below.

Added Web POST tests cover session/CSRF, forwarding of the explicit event payload,
Core rejection and unavailability. Added isolated Core HTTP tests cover Calendar
CRUD/persistence/workspace isolation, primary OWNER protection, and member
deactivation/session revocation/reactivation with actor attribution. No real provider is used.

The first deactivation regression failed with `BadSqlGrammarException` because
the PostgreSQL driver cannot infer the SQL type of `java.time.Instant` passed to
`JdbcClient.param`. `RbacService.deactivate` now converts the clock value once to
`java.sql.Timestamp`, using it for both account update and session revocation.
The final test proves deactivation rejects the old token and reactivation permits
a new login without reviving revoked tokens. This is a local code repair only,
not a deployed fix or a completion of the wider transactionality work in R4.

## Documentation reconciliation

| Previous item                                                  | Current evidence and corrected status                                                                                                                                                                             |
|----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Calendar create blocked by missing authentication context      | Calendar incident is resolved; interceptor includes `/v1/calendar/**`. September 15 has local CRUD/read-only Google handoff. New test verifies explicit Web payload persistence, not physical/browser acceptance. |
| RBAC and deactivation entirely deferred                        | `Rbac.kt`, V29, Users/Roles routes and September 14 deployment exist; important correctness gaps remain below.                                                                                                    |
| Invited-user rollout entirely pending                          | September 14 reports Core/Web image activation. Current installation/browser/hardware acceptance is not inferred from that report.                                                                                |
| Target resolution, policy classes, health/audit still new work | Existing implementation and September 6 closeout already cover bounded foundations; remaining stabilisation/coverage is kept distinct.                                                                            |
| HA configuration is operator-only                              | Probe/connect/disconnect routes, Web overlay and encrypted connection store exist; development env fallback also remains. Device import is still read-only.                                                       |
| Backup and audit integrity entirely future                     | SQL backup/restore verification, personal encrypted exports and HMAC chains exist; complete installation recovery is unproven.                                                                                    |
| Background state/events entirely absent                        | Gateway state refresh, button bindings and motion history exist; broad provider-neutral refresh/reconciliation and repeatable hardware acceptance remain open.                                                    |
| Streaming/TTS experiments are all active TODOs                 | Historical provider worklists are superseded; active Voice acceptance does not reopen provider discovery.                                                                                                         |
| Installer does not exist in any form                           | Migration and HTTPS preparation tools exist; no general fresh installer or existing-installation updater exists.                                                                                                  |

The original TODO file is retained at `TODO-history-before-2026-10-11.md` without
editing its bytes. SHA-256 at preservation:
`0f53b1b9216d6d5b28e631fbbd49c5bacb892f388f2a17dc2b8b517993580e5b`.
The active list separates completed groundwork, security gates, installer work,
physical acceptance and later product scope. Dated reports remain historical evidence.

## Critical security and behaviour review

These findings distinguish source-confirmed gaps from exercised behaviours.
They are not a claim of exploit testing against the live installation. No broad
RBAC/schema change was silently added to this preparation task.

| ID / severity                                | Evidence                                                                                                                                                                                                                                                                            | Impact and required follow-up                                                                                                                                                                                                                                                                       |
|----------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| R1 High, source-confirmed                    | `AuthenticatedRouteInterceptor.kt`: Calendar is registered for authentication but `permissionFor` has no Calendar mapping; null means skip RBAC. V29 has no Calendar permission keys.                                                                                               | Any authenticated member can reach shared local CRUD regardless of VIEWER/custom restrictions. Add explicit read/create/update/delete catalog permissions, non-destructive forward migration/default policy, and HTTP denial tests; audit all registered families for missing mappings.             |
| R2 High, source-confirmed                    | `RbacService.initializeUser` calls `ensureRoles` for every registration. It inserts default ADMIN/USER/VIEWER grants with `ON CONFLICT DO NOTHING` even after an owner removed them.                                                                                                | New invited registration can restore withdrawn standard role rights for existing members. Seed initial defaults only for newly created roles; test role reduction -> invite redemption -> unchanged grants.                                                                                         |
| R3 High correctness, source-confirmed        | Role create/update/delete controller passes `authenticatedUserId()` as `ownerId`; reads use `rbac.workspace(actor)`.                                                                                                                                                                | Delegated users with role permissions can create roles under their own UUID, invisible to the installation list; editing legitimate installation roles fails ownership lookup. Keep actor and workspace owner separate and test cross-workspace boundaries.                                         |
| R4 High, source-confirmed                    | RBAC deletes/inserts grants and assignments, changes account state, revokes sessions and writes audit in separate SQL operations without transaction demarcation in `RbacService`. `ensureRoles` is also not transactional for first setup.                                         | Failure/concurrency can leave partial rights, missing assignment or missing audit. Add transactions and invariant locking/failure tests; define who may promote another owner. Current owner/deactivation regressions cover success/protection, not atomic failure or every owner concurrency case. |
| R5 High for fresh setup, source-confirmed    | `/v1/auth/setup` is unauthenticated; `createOwner` locks against duplicate owner creation but has no administrator bootstrap proof.                                                                                                                                                 | Before the owner exists, first LAN caller can claim a fresh installation. Add expiring single-use local bootstrap authority before LAN onboarding; never reopen on existing data.                                                                                                                   |
| R6 High audit gap, source-confirmed          | Calendar controller/repository performs mutations without ActivityService. Interceptor returns RBAC 403 without an audit event. RBAC audit records type/actor/workspace but no affected account/role identifier.                                                                    | Calendar changes and permission refusals lack adequate traceability; RBAC target cannot be reconstructed reliably. Add minimal target/actor/correlation facts without event content or secrets. Preserve existing sealed rows.                                                                      |
| R7 High privacy policy gap, source-confirmed | Local Calendar and Google controller use `workspaceOwnerId`; Google token/grants are workspace-wide, and generic `integrations:read` permits event reads.                                                                                                                           | Owner-connected Google events can be shown to invited members; personal/shared calendar consent and permissions are undefined. Default privacy and explicit sharing must be decided before household pilot onboarding.                                                                              |
| R8 Medium availability, source-confirmed     | Web Calendar GET uses `Promise.all` for local and Google fetches. HTTP Google errors are ignored, but a thrown fetch rejects the entire load; there is no bounded upstream timeout here.                                                                                            | Local calendar can become unavailable on Google network failure even though HTTP-error tests pass. Add thrown-fetch/timeout tests and independent bounded optional-provider handling.                                                                                                               |
| R9 Medium API/UX, partially reproduced       | Test POST omitting `syncToGoogle` returned 400 `INVALID_REQUEST`: `Cannot map null into type boolean`. Explicit false matches current Web payload and passes CRUD. `LocalCalendar.kt` validates only title/order; UI uses UTC string slicing for editing and hardcoded German text. | Kotlin default does not currently establish an optional HTTP field. Reconcile typed defaults, bounded description/timezone, stable validation errors, timezone/DST editing and bilingual UI. Sync checkbox persists intent without implemented bidirectional sync.                                  |

Positive evidence: current authentication uses opaque hashed sessions/Argon2id;
Web mutations have session and CSRF boundaries; workspace identity comes from
server request attributes. The Calendar HTTP test proves isolation between two
synthetic independent workspace owners for explicit payload CRUD. It does not prove
VIEWER restrictions, which are missing (R1). OWNER role editing/primary-owner
deactivation are rejected, and deactivation invalidates member access in new tests.

Audit events are HMAC-sealed in owner/system chains using a separate 32-byte key,
with append transactions/chain-head locking and authorised retention anchors.
Existing tests cover tampering and actor attribution; key custody, audit completeness
and action/audit failure atomicity remain separate concerns. Shared device tests use
a mocked Nanoleaf adapter. Neither an adapter confirmation nor this test run is a
new independent measurement of a lamp or voice/audio sequence.

## Existing installer, configuration and runtime

| Area                  | Present safeguards                                                                                                                                                                                 | Gaps for Installer v1                                                                                                                                                                                                                                                                                                 |
|-----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `install-platform.sh` | Root gate, required bundle files, active Docker, ports 3000/18080, nonempty DB refusal, protected key modes, DB readiness, `pg_restore --exit-on-error`, Core/Web checks before gateway URL change | Requires existing dump/keys; no fresh mode, complete existing-state/symlink/lock guard, port 443 check, stage journal or safe retry. Config/keys can be overwritten when DB appears empty. Failure leaves partially installed state. It changes gateway config/restarts a service, outside fresh v1 authority.        |
| Bundle preparation    | ARM64 builds, 32-byte key length check, generated DB password, SHA256SUMS                                                                                                                          | Installer never verifies SHA256SUMS; no authenticated manifest/signature, immutable release identities or image-platform cross-check. Bundle contains DB, keys and provider secrets and uses developer paths/address defaults; no explicit protected Windows ACL before creation. Not a public distributable release. |
| HTTPS                 | Separate Caddy image/bundle, self-signed leaf with `CA:FALSE`, private key on Pi, trusted curl check in activation                                                                                 | Main bundle omits Caddy/TLS preparation. HTTPS activation overwrites configuration and generates a new certificate without a complete key/state guard. Caddyfile and SAN hardcode `192.168.1.116`/`kyrion-node.local`; client trust/expiry/renewal is manual.                                                         |
| Compose               | DB unexposed; Web/Core loopback; private network; non-root Core/Web, read-only root, dropped caps and no-new-privileges; healthchecks/memory limits                                                | Mutable local/base tags, development `build` contexts, environment passwords/optional tokens, writable Core key directory and Caddy bound to all host interfaces on 443. No portable manifest or CPU limits. Fresh installer must use its own reviewed template.                                                      |
| Runtime health        | Existing cached ARM64 Core image contains `/usr/bin/curl`; Web/Caddy use wget                                                                                                                      | Application/JAR and Web builds passed, but no new ARM64 container image or current-source runtime was built/run. Validate each health dependency for the signed release; cached image check is limited evidence. Caddy health uses `--no-check-certificate`, which cannot establish client trust.                     |
| Configuration         | Placeholder env examples and server-only credential/key ownership; Core Google env configuration exists                                                                                            | Pi Compose does not forward Google env keys and platform example documents only a subset. Avoid silently claiming Google setup works on a fresh Pi. Optional AI address is a remote capability; container loopback is not the host's AI service.                                                                      |
| Keys                  | Credential AES-GCM and HMAC audit keys are separate; migration preserves originals                                                                                                                 | `CredentialCipher`/`ActivityIntegrity` can create missing keys. Writable deployment key mount permits silent new keys after loss. Add deployment load-only mode/read-only mounts and explicit startup validation; never rotate keys automatically on recovery.                                                        |

`prepare-platform-bundle.ps1`, `enable-platform-https.sh`, and legacy migration
helpers were **not executed**. Static review does not establish preservation on a
real node. New installer test fixtures must compare unchanged paths/modes/services
for every existing-state refusal, including stopped/partial installations.

## Backup and restore assessment

- Existing `backup.ps1` uses `pg_dump`, exports a dump and records checksum/version,
  initially `restoreVerified: false`. It targets the development container/path by
  default; these defaults are not a Pi recovery workflow.
- `verify-restore.ps1` creates a random database inside its selected PostgreSQL
  container, restores and checks Flyway/public table facts, then drops that temporary
  database. It does not overwrite the active DB, but shares its engine/resources;
  do not run it on the owner's engine for this task. Manifest verification is
  conditional: a missing manifest currently does not block restore verification.
- SQL verification does not prove login, roles, calendar content, provider credential
  decryption or audit integrity. Keys are outside PostgreSQL and must be preserved
  separately under protected storage; wrong/missing keys make a dump insufficient.
- Personal passphrase-encrypted exports are bounded personal-data recovery, not a
  backup of accounts/devices/integrations/calendar or the complete platform.
- Gateway config, radio/coordinator state, Matter fabrics, HA and TLS coverage are
  not orchestrated into one verified recovery manifest. No backup/restore was run
  with owner data during this review.

## Verification performed

Commands were executed locally on Windows with installed dependencies. Core
integration tests explicitly override datasource URL/user/password to their own
PostgreSQL 17 Testcontainer and use temporary test key files. No `bootRun`, Compose
`up`, production dump/restore, privileged installer, SSH or live device request ran.

| Check                                                                                                     | Result                                                                                                                                                   |
|-----------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Original focused YouTube test                                                                             | Reproduced compileTestKotlin failure: missing `gateways` and `commands`                                                                                  |
| Core `gradlew.bat test bootJar --console=plain` after initial repair                                      | 170 tests passed; boot JAR built                                                                                                                         |
| Added Calendar optional-field probe                                                                       | Failed: omitted Boolean -> HTTP 400; retained as R9, not misreported as a repaired API                                                                   |
| Calendar targeted test with explicit Web payload                                                          | Passed; persistence, CRUD and independent workspace isolation                                                                                            |
| First added member-deactivation regression                                                                | Reproduced PostgreSQL Instant binding failure; fixed by explicit JDBC Timestamp conversion                                                               |
| Final Core `gradlew.bat test bootJar --console=plain`                                                     | 173 tests passed, zero failures/errors/skips; boot JAR built                                                                                             |
| Web `pnpm test`                                                                                           | 101 tests passed in 37 files, including five added POST regressions                                                                                      |
| Web `pnpm lint`                                                                                           | Passed, including final rerun                                                                                                                            |
| Web `pnpm exec tsc --noEmit`                                                                              | Passed, including final rerun                                                                                                                            |
| Web `KYRION_BUILD_DIRECTORY=.next-review pnpm build`                                                      | Passed, 89 routes; separate ignored build output, no dev server restart                                                                                  |
| Platform `docker compose --env-file .../.env.platform.example -f .../compose.platform.yml config --quiet` | Passed using placeholders; no services started                                                                                                           |
| PowerShell parser on bundle/HTTPS/preflight/backup/restore scripts                                        | Passed, zero syntax errors in five files                                                                                                                 |
| POSIX shell parse on migration/HTTPS/runtime scripts                                                      | Passed with WSL `sed 's/\r$//' FILE \| sh -n` and pipeline failure propagation; no script execution                                                      |
| Cached ARM64 Core image health prerequisite                                                               | `docker run --rm --network none --entrypoint sh kyrion/core:pi-local -c 'command -v curl'` found curl; no mounts, published ports or application startup |
| Formatting / diff hygiene                                                                                 | `git diff --check` passed; no standalone Core formatter/linter task configured                                                                           |
| Documentation consistency                                                                                 | Local Markdown file links passed in ten reviewed documents; original TODO snapshot hash matches its preserved source                                     |

The added optional-field probe initially failed and was narrowed to the payload
actually sent by Web (including explicit false). No broad JSON mapper change was
made. Final tests retain the successful real-contract path; R9 records the uncovered
default-field limitation. Debugger tooling was unavailable, so diagnosis used the
isolated MockMvc response/exception, not a running production JVM.

ShellCheck is not installed in the checked environment. POSIX parsing is a syntax
check, not shell lint or behavioural acceptance. No new ARM64 image builds, fresh
Debian installation, deployment restore, browser visual review, LAN TLS/client trust,
reboot/network-loss or physical hardware acceptance is claimed. AI/Gateway/Voice and
the independent public website code are unchanged and their full suites were not run.

## Changes and next step

Changed production file: `security/Rbac.kt` (explicit JDBC timestamp binding in
account state changes). Changed test files: YouTubeLinksTest,
AuthenticationPersistenceIntegrationTest and Web Calendar route.test.ts.
Documentation: consolidated TODO plus preserved historical
snapshot, status/context/roadmap/README pointers, corrected HA setup guide, this
review, Installer v1 plan and proposed ADR 0022. No production TypeScript,
deployment script, Compose config, secrets or migration was changed.

Next implementation starts with R1-R5 and their focused regressions, followed by
the read-only preflight/signed public bundle slice in the [plan](../installer-v1-plan.md).
R6/R7 and recovery gates remain required before pilot acceptance. Detailed future
security tests, file structure, setup flow, error codes and clean-room acceptance
are defined there. No deadline, completed installer or new physical success is implied.
