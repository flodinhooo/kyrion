# Security, RBAC and Installer Readiness Hardening — 2026-10-11

This is the implementation closeout after the earlier
[readiness review](2026-10-11-installer-readiness.md). It supersedes that review's
open code findings while preserving its original evidence. No production database,
credentials, deployment, migration execution against installed systems, commit or
push was used. PostgreSQL tests used Testcontainers and temporary keys only.

## Implemented security corrections

| Finding                                     | Result and boundary                                                                                                                                                                                                                                                                                           |
|---------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| R1 Calendar authorization                   | Four explicit CRUD permissions, checked at HTTP and service boundaries; workspace-derived queries reject foreign IDs. Unmapped protected routes fail closed. No new personal-calendar schema is invented.                                                                                                     |
| R2 Restored grants                          | Registration never seeds roles. Initial owner seeding only grants newly inserted roles; repeats preserve grants and assignments. Concurrent invitations preserve an owner-revoked permission.                                                                                                                 |
| R3 Actor/workspace confusion and escalation | Mutation methods accept the actual actor and derive its workspace. Delegates cannot assign OWNER, manage owners, change their own roles, or manipulate permissions above their current ceiling. Cross-workspace target validation precedes session revocation.                                                |
| R4 Atomicity                                | Role grants/assignments, activation/session revocation, setup, registration and local calendar mutation include audit in the same transaction. Workspace advisory locks serialize permission validation and mutations. Transactional identity flows avoid last-seen session row locks before workspace locks. |
| R5 First-owner takeover                     | Protected-file, 256-bit base64url bootstrap, 30-minute expiry, constant-time comparison, bounded backoff and permanent initialization state. The existing global advisory lock admits one owner. Failed setup rolls back marker, user, roles, session and audit. Existing users close setup during V31.       |
| R6 Audit gaps                               | Actual actor/workspace, target UUID and correlation are recorded for RBAC/local calendar writes. HTTP permission denials are recorded. Google writes persist intent and outcome, without titles, descriptions, provider IDs or tokens. Existing seals are untouched.                                          |
| R7 Private Google exposure                  | Google APIs/OAuth use the authenticated identity. Catalogue filtering hides another account's Google metadata; Google connections are excluded from shared devices and room mutation paths. Local events remain explicitly shared, requiring owner-granted calendar permissions.                              |
| R8 Optional Google outage                   | Thrown optional fetches no longer discard local events; optional request has a ten-second timeout. Local Core fetch remains a separate timeout follow-up.                                                                                                                                                     |
| R9 JSON contract                            | Missing/null syncToGoogle means false; true/false work; strings, numbers and containers fail. Missing timezone means UTC, invalid zones and oversized descriptions are rejected. No global Jackson mapper change.                                                                                             |

The immutable primary owner remains protected. An owner may assign OWNER to another
member; non-owner administrators cannot. Existing owner roles are not silently
demoted. Deactivation does not revive previously revoked sessions on reactivation.
Role keys remain immutable on update; display names and grants are editable.

Default ADMIN lacks some default USER/VIEWER personal permissions. The permission
ceiling deliberately prevents managing those roles/targets until the owner chooses
a bounded delegation. This does not grant administrators access to private data.
Invitations are authorized by invitations:create, including explicit delegation;
canInvite now reflects this capability rather than original-owner identity.

## Files and implementation decisions

Architecture is recorded in [ADR 0023](../adr/0023-security-bootstrap-and-delegation.md).
No new dependency or service was introduced.

- Core security: Rbac.kt, LocalAuthenticationService.kt, AuthSessionService.kt,
  AuthenticationController.kt, AuthenticatedRouteInterceptor.kt,
  UserAccountRepository.kt, JdbcUserAccountRepository.kt, new FirstOwnerBootstrap.kt.
- Calendar/provider boundaries: LocalCalendar.kt, GoogleIntegration.kt,
  IntegrationCatalog.kt, DeviceCatalog.kt and the bounded Google exclusion in
  RoomController.kt. Provider HTTP calls stay outside long database transactions.
- Persistence/configuration: additive V31, application.yml, placeholder-only
  infrastructure/.env.example, Compose bootstrap file path. No runtime services started.
- Web: transient setup secret forwarding in session-cookie.ts, DE/EN setup input
  in auth-form.tsx/messages.ts, independent optional Google fetch in calendar route.
- Tests: AuthenticationPersistenceIntegrationTest.kt, LocalAuthenticationServiceTest.kt,
  new FirstOwnerBootstrapTest.kt and session-cookie.test.ts, Calendar route tests.
  The earlier YouTubeLinksTest fixture repair is retained and verified.
- Docs: this closeout, TODO, readiness update, status/context pointers,
  authentication boundary, Installer v1 plan and ADR. Earlier preparation edits
  and the byte-preserved TODO history remain intact.

## Regression and migration evidence

New cases cover parallel invitations after permission withdrawal, delegated
administration and privilege escalation, foreign session protection, OWNER/ADMIN/
USER/VIEWER boundaries, concurrent bootstrap winners, invalid/missing/reused secrets,
expiry/backoff, rollback/retry, concurrent permission revocation, audit-storage
failure rollback, optional Calendar fields and invalid values, Calendar write
denials, private Google HTTP/catalogue visibility and correlated provider audit.

V31 creates installation_bootstrap_state and adds four permission definitions. It
does not rewrite existing role grants, delete users or change appointment records.
The isolated upgrade test creates a representative V30 schema with an existing
account and restricted role, applies V31 and verifies that the account/grant remain,
setup closes, and deleting the synthetic account does not reopen it. This is
synthetic test data, not a copy of a production database.

Tests also install a temporary PostgreSQL trigger that rejects audit inserts.
Role permission/assignment changes, account/session revocation, registration and
local Calendar creation roll back. The trigger is removed in finally. Separate
owner setup rollback verifies that the original setup secret remains retryable.

| Final check                                                                                                                                              | Actual result                                                                                                                                           |
|----------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| Core gradlew.bat test bootJar --console=plain                                                                                                            | Passed: 187 tests, zero failures/errors/skips; Boot JAR built. Includes 36 isolated PostgreSQL HTTP/persistence tests and the V30-to-V31 upgrade probe. |
| Web pnpm test                                                                                                                                            | Passed: 104 tests in 38 files.                                                                                                                          |
| Web pnpm lint                                                                                                                                            | Passed: ESLint exit 0.                                                                                                                                  |
| Web pnpm exec tsc --noEmit                                                                                                                               | Passed: exit 0.                                                                                                                                         |
| Web KYRION_BUILD_DIRECTORY=.next-review pnpm build                                                                                                       | Passed: production compilation, TypeScript and 89 routes; separate build output, no running server restarted.                                           |
| docker compose --env-file infrastructure/nodes/kyrion-node/.env.platform.example -f infrastructure/nodes/kyrion-node/compose.platform.yml config --quiet | Passed with placeholders; no service startup.                                                                                                           |
| git diff --check                                                                                                                                         | Passed after final documentation edits.                                                                                                                 |

No standalone Core formatter/linter is configured; Kotlin compilation and diff
hygiene ran. The unchanged deployment scripts retain the previous syntax-check
evidence in the readiness review, not new behavioural acceptance. AI/Gateway/Voice
suites were not rerun because those services were unchanged. No failed/skipped
relevant test is being hidden by an exclusion.

## Operational risks and remaining acceptance

Implemented and automatically tested does not mean deployed or physically accepted.
Installer v1 implementation can start from this baseline, but pilot release remains
blocked on its operational security and recovery gates:

- Provision/bootstrap delivery, parent-directory/mount permissions and private
  TLS transport are installer responsibilities. Core enforces POSIX file permissions;
  Windows ACL provisioning and target Linux permission behaviour were not accepted
  on hardware. No remote token renewal/reset endpoint exists. After expiry, local
  renewal must repeat fresh-install checks and must never reopen an initialized DB.
- Bootstrap throttling is process-local and resets on restart; the permanent DB
  state and high-entropy proof remain authoritative. Tests do not establish a
  multi-instance deployment; Installer v1 is a single Core instance.
- Existing orphan roles from the old delegated-workspace bug need deliberate
  operator review if present. No legacy role is deleted or reassigned automatically.
- External provider success cannot be rolled back by PostgreSQL. If final audit
  persistence fails, the durable proposed event remains for reconciliation; no
  distributed transaction or reconciliation worker is claimed.
- Signed public artifacts, protected deployment passwords, load-only credential/
  audit keys, and complete deployment backup/isolated restore are still unimplemented
  Installer v1 release gates. Current key creation must not be used as restore policy.
- Calendar UI still has timezone/DST editing and bilingual review work. syncToGoogle
  saves intent only; bidirectional sync and its checkbox promise remain follow-ups.
- No fresh Debian ARM64 install, live Google account action, real device success,
  reboot/network-loss, browser visual or restore acceptance was performed.

The focused security implementation is a foundation for the Installer implementation
sprint, not authorization to deploy or a full pilot/production readiness claim.
