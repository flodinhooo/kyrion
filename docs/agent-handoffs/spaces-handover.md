# Spaces — Agent 3 final handover

Date: 2026-10-30. Scope: this agent's Spaces work only. Technical documentation is
English in accordance with repository policy. Development is paused; this closeout
adds documentation only. No merge, deployment or production migration occurred.

## Ownership and recorded changes

- Branch: `feat/kyrion-spaces`.
- Worktree: `E:/dev/Kyrion/kyrion/.worktrees/kyrion-spaces`.
- Base: `2740399`; Milestone 01: `9740b88cdce710e37012ecf482c39876b37bcacf`.
- Milestone 02: `94f7f4efb81db19061a9b258eb49842189d3ced8`.
- Both implementation milestones are committed. The worktree was clean before this
  handover was added. Only this handover is staged for the documentation commit;
  its resulting SHA can be found with `git log -1 -- docs/agent-handoffs/spaces-handover.md`.

Original assignments were Spaces, membership, invitations, migration, onboarding,
tenant-aware authorization and bilingual product presentation, followed by verified
Business identities, domain ownership, protected local OWNER recovery and a wider
isolation audit. The final instruction superseded further implementation with a
documentation-only closeout. Other agents' knowledge, calendar, stabilization and
Velora work is not attributed to this agent or included in the test claims below.

Primary evidence and detailed procedures:

- [Milestone 01 report](../status/kyrion-spaces-agent-3.md).
- [Milestone 02 report and exact commands](../status/kyrion-spaces-milestone-02.md).
- [Spaces model](../kyrion-spaces.md), [identity and recovery runbook](../business-identity-and-recovery.md).
- [Tenant audit matrix and missing tests](../spaces-tenant-audit.md).
- [ADR 0031](../adr/0031-kyrion-spaces.md) and
  [ADR 0032](../adr/0032-business-identity-and-local-recovery.md).

The Milestone 01 report's statements that domain enforcement and recovery are
unimplemented describe that earlier checkpoint; Milestone 02 supersedes them.

## Implemented components and boundaries

### Spaces, memberships and invitations

HOME and BUSINESS share one implementation. Ordinary membership is immutable and
exactly one Space per account; there is no universal personal login or Space
switcher. Existing root-owner UUIDs remain resource ownership keys and become Space
IDs. First-owner bootstrap retains the existing setup protection and atomically
creates the Space and OWNER. Existing installations retain bootstrap state.

`SpaceService.kt` owns current-Space metadata, OWNER settings, default/custom roles,
invitation metadata and revocation. Existing `/users` and `/roles` management is
reused. `/v1/auth/me` supplies current Space metadata. Invitations use 256-bit random
codes with SHA-256 storage, default 24-hour expiry/one use, bounded to 1–168 hours
and 1–20 uses. Advisory and row locks make consumption/account/role creation atomic.
Revocation is idempotent; inviter authority is checked again at acceptance. OWNER
invitations and delegation exceeding effective permissions are forbidden. Listing
is bounded to 200 records. Existing session, CSRF, audit and rate-limit conventions
remain in use; issuance throttles are process-local, not distributed infrastructure.

The bilingual Web app provides first-run setup, `/settings/space`, member links,
current Space/type/role, invitation creation/copy/revocation and signup acceptance.
Local links use a fragment token removed from browser history during acceptance.
They require network reachability to the installation. Public website changes are
minimal German/English Home/Business/Spaces presentation, not cloud administration.

### Verified Business identity and domain policy

Core security implementation is under
`services/core/src/main/kotlin/dev/kyrion/core/security/`, principally
`BusinessIdentityController.kt`, `BusinessIdentityProof.kt`,
`BusinessIdentityService.kt` and `TenantBoundary.kt`.

Pending email replacement is separate from the current verified identity. SMTP
proofs are hashed, single-use, valid 15 minutes and consumed transactionally.
Resending invalidates the previous proof; limits are one request/minute and five/hour
per account or invitation. Public invitation-email requests return uniform 202 for
syntactically valid inputs without revealing unrelated accounts or invitations.
Registration proof binds recipient, invitation and Space. Profile/email changes
cannot carry old verification to a new address. Existing emails are not auto-verified.

Domains use IDNA/STD3 normalization and exact matching; a subdomain needs its own
entry. Mailbox syntax deliberately excludes SMTPUTF8, quoted/display-name addresses,
wildcards, IP domains and header injection. Mailbox local-part case is preserved.
Domain ownership is independent of mailbox ownership: OWNER configures unpredictable
Space-bound `_kyrion-verification.<domain>` TXT challenges, stored hashed, expiring
after 30 minutes. Successful DNS evidence lasts 30 days and can be invalidated or
rotated. Resolution trusts the configured resolver/network, without application
DNSSEC validation or continuous ownership monitoring.

Strict activation requires SMTP, current DNS evidence, allowed SMTP-verified emails
for every enabled member, provisioned local recovery and explicit confirmation to
revoke outstanding invitations. It cannot exclude the current OWNER/member set or
be bypassed by changing Business to Home. DNS expiry blocks new enrollment, email
changes and reactivation while preserving current members' access. OWNER can disable
the policy despite expired evidence. Explicit host-admin local attestation remains
distinct from SMTP verification and cannot satisfy strict mode. HOME defaults and
existing policies remain OFF.

API additions: authenticated `/v1/identity/email`, `/email/verify`,
`/business`, `/business/challenge`, `/business/verify`, `/business/suspend`
(all relative to `/v1/identity` after the first path); public
`POST /v1/auth/registration-email`; optional email/proof registration fields.
Controllers define exact methods and request types. `/settings/identity` and its
allowlisted Web proxy expose bilingual status, resend, domain/policy and recovery
instructions. No recovery secret is stored in browser localStorage.

### Protected local OWNER recovery

`LocalSecurityAdmin.kt` and `LocalOwnerRecovery.kt` implement an interactive JVM
administrative entry point, with no HTTP recovery route and no application providers
or schedulers started. Normal Core main is explicitly pinned in Gradle.

Provisioning requires the current root OWNER password and installation database/audit
configuration. Recovery requires a protected per-Space host file plus separately
stored offline material; its hashes bind installation, Space and purpose. A consumed
code rotates to a replacement and opens a five-minute one-use recovery session.
Completion requires a different 12–200 character password, rotates recovery material
and revokes OWNER sessions, pending email proofs and invitations. It creates no
account, role, automatic login or cross-Space authority. Offline credentials expire
after one year; authenticated rotation is supported.

The CLI requires `System.console()` before connecting, hides secret input and checks
POSIX modes or Windows ACLs. It verifies the existing audit chain before writing;
failures and successes are audited, and audit failure rolls back security writes.
There is no master password, staff identity, support bypass or recovery without
installation control. Database/audit/host administrators remain trusted. Restoring
old backups may restore spent material: rotate credentials after restoration.
Actual interactive production acceptance remains outstanding.

### Tenant enforcement and deliberately disabled paths

`TenantBoundary` resolves active database membership, rather than trusting request
Space IDs. RBAC joins role scope to the actor's Space. Explicit actor/shared/personal
checks and worker workspace validation are tested. Nested database constraints cover
room/connection, gateway node/command, voice satellite/session and HA device/connection.
HA refresh, Zigbee queued execution and gateway authentication/heartbeat gained
active-workspace checks. Voice pending actions and acknowledgements bind Space,
session, satellite and turn. K-AI streaming revalidates actor/session/permissions and
current model policy before invocation and during event delivery; rejected unused
reservations are released without charge. Existing cloud approval stays explicit.

Business satellite/browser voice and direct Web speech synthesis are blocked because
a reviewed per-person principal is missing. Legacy device proposals are blocked for
Business and Home with explicit K-AI policy because their old path bypasses routing
and budgets. Manual device control remains available. Browser speech preview/entry
uses trusted shell policy; this does not govern unrelated OS services used by users.

`SingleSpaceRuntimeGuard` still refuses more than one Space at application startup.
Two-Space database/service tests are security probes, not supported multi-Space
runtime provisioning. Existing calendar/OAuth, Spotify, personal preferences/memory,
conversation and credential paths were inspected with existing scoped tests retained;
this is not exhaustive hardware, provider-race, cache, stream or worker certification.
Knowledge/RAG/documents/vectors from another agent are absent here; their endpoint is
tested as unavailable (404), not certified isolated. See the audit matrix for precise
coverage and missing tests. No complete tenant-isolation claim is made.

## Migrations and data preservation

- V37 `kyrion_spaces`: Space metadata/default role, generated user Space membership,
  immutable assignment, scoped roles and bounded invitation metadata. Ambiguous root
  ownership, nested membership and incompatible assignments fail with actionable
  `SPACES_MIGRATION_*` diagnostics. No company is inferred from email.
- V38 `business_identity_and_local_recovery`: installation identity, Business policy,
  domain evidence, current/pending account email identity, email challenges, invitation
  email constraint, recovery material/sessions and nested ownership constraints.
  Invalid nesting aborts with `TENANT_NESTED_OWNERSHIP_INVALID`.

Migrations are additive. Existing users, effective OWNER/roles, resource ownership
keys, encrypted credentials, bootstrap state and audit history are preserved. No
historical identity/domain is marked verified. These migrations ran only in disposable
test databases, not production. Do not change either committed migration during closeout.

## Configuration and operations

JDK 21, PostgreSQL and the existing Node/pnpm toolchain are required. Spring Mail is
the sole new application dependency, managed by the existing Boot BOM. SMTP requires
STARTTLS and certificate validation; it has no insecure/log-only fallback. Implicit
TLS port 465 is not implemented. No SMTP means no SMTP verification or strict activation;
privileged local attestation is a distinct alternative, not a bypass.

See `infrastructure/business-identity.env.example`, isolated
`identity/smtp.properties`, and the identity runbook for exact startup/CLI commands:
`KYRION_IDENTITY_SMTP_HOST`, `_PORT` (587), `_USERNAME`, `_PASSWORD`, `_FROM`, with
existing `_FILE` support; optional `KYRION_IDENTITY_DNS_SERVER`. No credential values
are recorded here. The runbook covers Linux private files, Docker UID 10001 and
Windows ACLs/PowerShell quoting for Boot `PropertiesLauncher` and `LocalSecurityAdmin`.
Existing installer/Compose/Docker templates were not changed by this milestone;
operators must supply and protect SMTP/host recovery configuration explicitly.
Do not restart services merely to inspect this handover.

## Verification record

No suites were rerun for this documentation-only closeout. These are the recorded
final results of the implementation commits, not validation of a later merged tree:

| Check | Milestone 01 | Milestone 02 |
|---|---:|---:|
| Core | 244 tests / 47 suites | 266 tests / 51 suites; zero failures/errors/skips |
| Real PostgreSQL integration tests | Included | 66, included in Core total |
| Web | 170 tests / 52 files | 186 tests / 55 files |
| Website Playwright | 28 | 28 |
| Local Web browser flows, mock Core | 4 | 6 |

Core `bootJar`, Web/website lint, TypeScript checks and production builds passed.
ktfmt 0.54 checked the ten newly added Kotlin files; this is not a repository-wide
format certification. Website changed-file Prettier and `git diff --check` passed.
Commands from the dedicated worktree (Web block from `apps/web`):

```powershell
$env:JAVA_HOME=(Get-ChildItem .local-tools/jdk21 -Directory | Select-Object -First 1).FullName
& services/core/gradlew.bat -p services/core "-Porg.gradle.java.installations.paths=$env:JAVA_HOME" test bootJar --console=plain
& services/core/gradlew.bat -p services/core "-Porg.gradle.java.installations.paths=$env:JAVA_HOME" test --tests dev.kyrion.core.security.IdentityTransportTest --console=plain
# apps/web
pnpm exec next typegen
pnpm lint
pnpm exec tsc --noEmit
pnpm test
pnpm build
# repository root
pnpm --filter website lint
pnpm --filter website typecheck
pnpm --filter website build
pnpm --filter website test
pnpm --filter website exec playwright test --config playwright.spaces.config.ts
pnpm --filter website exec prettier --check src/locales/en.json src/locales/de.json tests/spaces-web.flow.ts
git diff --check
```

Security tests cover concurrent bootstrap/redemption/verification, migration
preservation, delegation/OWNER denials, token expiry/replay/revocation, domain activation
lockouts, recovery rotation/audit and cross-Space denials. Real loopback SMTP rejects
a relay lacking STARTTLS before AUTH/DATA; real loopback UDP DNS tests split TXT
strings. Business service tests use deterministic delivery/DNS substitutes. Windows
ACL tests and a packaged CLI negative smoke passed: redirected execution exits 1
before database access, as intended. No actual mailbox, customer DNS, paid cloud
provider or physical device was acceptance-tested by these milestones.

Resolved intermediate failures included missing JDK 21 (ignored local tool installed),
bootstrap JSON defaults, PostgreSQL timestamp typing, stricter invitation expectations,
additional audit events, separate CLI main-class selection, DNS TXT parsing, JVM/DB
clock skew on invalidation/reactivation, test-double compatibility and locale/browser
assertions. One Testcontainers startup timeout passed unchanged on retry. An initially
unquoted PowerShell loader argument failed and was corrected in the runbook. No final
suite failure remains recorded. Existing Kotlin/Gradle deprecations and Next worktree/
standalone-server warnings are non-fatal. Interactive Linux/Docker recovery and combined
parallel-branch validation remain unperformed, not successful results.

## Cross-agent integration

Read-only root inspection at closeout: `refresh/product-credibility` at `082b661`.
Root has `V35__personal_context_controls.sql`, `V36__personal_knowledge.sql` and
`V37__personal_calendar_context_opt_in.sql`. Its V37 conflicts with Spaces V37.
This is an integration/deployment blocker; numbering/applied history needs an explicit
decision. V38 was free when this branch was implemented; recheck the union later.

Current root uncommitted website audience/presentation changes and the calendar
recovery worktree were left untouched. Earlier parallel context/knowledge/K-AI changes
are described in the milestone report; their current commit status is not assumed.
Potential shared files include Core build/authentication/RBAC/interceptors, K-AI
orchestration/settings/streams, context contracts, Web shell/chat/voice, locale files
and website presentation. Preserve knowledge permission grants and Spaces guards
together. Do not cherry-pick or merge as part of this closeout.

Required integration order: inventory applied migration histories; resolve migration
collision; combine contracts/permission grants and build configuration; bind knowledge
and asynchronous principals explicitly; run combined PostgreSQL and two-Space security
tests plus Web flows. Keep unsupported paths and multi-Space startup guarded throughout.

## Open TODOs

There are **10 open items: 1 P0, 6 P1, 2 P2 and 1 P3**. P0 below is a guarded
integration/deployment blocker, not a demonstrated live exploit.

### SPACES-001 — Resolve duplicate migration V37
- Priority: **P0**. Components: Flyway, Spaces and calendar/context integration.
- Problem/current state: two branches independently committed different V37 files;
  combined migration history has not been validated.
- Next steps: inventory applied histories and agree a compatible integration plan;
  test clean creation and upgrades from each supported history without rewriting
  applied production migrations.
- Dependencies: calendar/context owner and integration maintainer.
- Acceptance: unique, validated combined history preserves accounts, permissions,
  ciphertext and audit rows; both upgrade and fail-closed diagnostics tested.
- Risks: checksum failures, blocked startup or unsafe ad hoc renumbering/data mapping.

### SPACES-002 — Integrate knowledge isolation
- Priority: **P1**. Components: ContextBuilder, KnowledgeContextAssembler, knowledge
  controller/service/repository, blobs, embeddings and retrieval workers.
- Problem/current state: implementation absent here; unavailable endpoint is guarded,
  but parallel document/RAG/vector work has no combined Spaces certification.
- Next steps: adopt explicit TenantBoundary actor/personal/shared contracts and add
  two-Space upload/list/download/delete, guessed document/chunk ID, lexical/vector,
  blob/index, embedding/retry and streamed citation/context tests.
- Dependencies: knowledge/context agent's final commits and contracts.
- Acceptance: reads/writes/retrieval/jobs deny other Space and other user's private
  data before storage/provider calls; source prompts contain only permitted content.
- Risks: cross-tenant document or memory disclosure after an unchecked merge.

### SPACES-003 — Complete worker, provider and stream isolation audit
- Priority: **P1**. Components: integrations, discovery, gateways, caches, async jobs,
  retries, event streams and service credentials.
- Problem/current state: targeted guards and tests exist; lifecycle coverage is
  incomplete. Multi-Space startup remains blocked.
- Next steps: use audit matrix to test stale sessions, guessed IDs, altered arguments,
  concurrent suspension, explicit async propagation and event/cache scoping across
  two Spaces; verify zero downstream provider calls on denial.
- Dependencies: combined integration/runtime branches and test fixtures.
- Acceptance: every supported execution path has evidence; retain startup guard until
  independent review approves all relevant boundaries.
- Risks: ambient identity loss, stale cache authority or cross-Space streamed events.

### SPACES-004 — Establish Business voice principals
- Priority: **P1**. Components: Velora, satellites, STT/TTS, Web voice and Core policy.
- Problem/current state: Business voice intentionally disabled; root-owner satellite
  identity cannot safely represent individual employees.
- Next steps: define authenticated least-privilege per-person/session authority,
  propagate Space and policy through recognition/synthesis/tools and add revocation,
  cloud-consent and two-Space voice tests before enabling.
- Dependencies: Velora/K-AI owners and reviewed principal contract.
- Acceptance: no Business speech/provider/tool execution bypasses identity, consent,
  budgets or policy; disabled states remain accurate until proven.
- Risks: shared-device privilege escalation or unintended vendor-cloud disclosure.

### SPACES-005 — Route legacy proposals through K-AI authority
- Priority: **P1**. Components: legacy proposals, model routing, budgets and device tools.
- Problem/current state: legacy proposal path blocked for Business/explicit Home AI
  policy; manual controls work.
- Next steps: replace bypassing execution with existing typed Core validation,
  routing/approval/accounting; test manipulated tools, stale policy and denial calls.
- Dependencies: stable K-AI orchestration and agent integration.
- Acceptance: no alternative path evades policy or per-message cloud approval; charge
  and audit semantics tested before removing guard.
- Risks: policy bypass, unwanted cloud use or incorrect usage accounting.

### SPACES-006 — Validate deployed SMTP and DNS trust
- Priority: **P1**. Components: email delivery, resolver, domain lifecycle and operations.
- Problem/current state: deterministic and loopback tests pass; no real customer
  mailbox/domain acceptance. DNSSEC is not validated by the application.
- Next steps: run operator-controlled STARTTLS delivery/certificate failure and DNS
  challenge/rotation/expiry tests; document trusted resolver/network requirements
  and ownership-change re-verification procedure without logging proofs.
- Dependencies: separately authorized test mailbox/domain and operator configuration.
- Acceptance: genuine mailbox proof and DNS evidence work; failures remain closed;
  policy activation/renewal does not lock out existing OWNERs.
- Risks: mail misconfiguration, resolver spoofing, expired ownership evidence.

### SPACES-007 — Accept recovery on supported hosts
- Priority: **P1**. Components: local CLI, Windows ACLs, Linux/Docker files and backups.
- Problem/current state: service tests/ACL checks/negative packaged smoke pass; real
  interactive production lifecycle has not been acceptance-tested.
- Next steps: follow runbook in isolated Windows and Linux/Compose installations;
  test provisioning, open/expiry/retry/complete/rotate, audit failure, restore and
  cross-Space rejection; verify private file ownership and offline storage practice.
- Dependencies: operator access, test backups and deployment-specific UID/ACL setup.
- Acceptance: authorized recovery succeeds without HTTP bypass; replay fails;
  sessions/password/code rotate and sealed audit survives; restored material rotated.
- Risks: insecure file permissions, lost recovery material or backup replay.

### SPACES-008 — Validate combined branch contracts and UI
- Priority: **P2**. Components: shared RBAC/build/K-AI/Web shell/chat/locales/website.
- Problem/current state: branch-local suites pass, combined parallel tree untested.
- Next steps: resolve explicit file conflicts preserving both grants and guards;
  rerun combined compilation, lint/types/build, security suites and bilingual flows.
- Dependencies: SPACES-001 and other agents' handovers/commits.
- Acceptance: no lost features or security gates; final merged-tree evidence has
  reproducible commands/counts and no duplicated product claims.
- Risks: silent permission loss, disabled-voice regression or misleading website copy.

### SPACES-009 — Define security-record retention and maintenance
- Priority: **P2**. Components: expired challenges/invitations/recovery sessions, audit,
  pending-action lifecycle and operator procedures.
- Problem/current state: expiry/consumption is enforced; broader cleanup and operational
  retention acceptance were not delivered as a complete lifecycle feature.
- Next steps: inventory retention obligations and bounded caches; design scoped cleanup
  preserving forensic evidence, then test expired/live-record separation and retries.
- Dependencies: existing retention/backup owners and worker isolation work.
- Acceptance: bounded storage/cache lifecycle without deleting required audit evidence
  or reviving consumed tokens; offline operation preserved.
- Risks: unbounded stale data or destructive cleanup of recovery/audit evidence.

### SPACES-010 — Keep managed portal and support work explicitly planned
- Priority: **P3**. Components: future portal, installation registration, licensing,
  pooled entitlements/budgets and SUPPORT_OPERATOR design.
- Problem/current state: design only; no cloud login/billing/relay/support grants or
  global administrative role implemented. Existing per-actor budgets are not a
  completed pooled Business billing model.
- Next steps: plan separate reviewed contracts after isolation is certified; require
  separate support identities, customer-initiated temporary scoped revocable grants,
  MFA, audit and sensitive-data restrictions.
- Dependencies: product decision, isolation review and explicit future authorization.
- Acceptance: local-only installations remain independent; no implicit OWNER bypass
  or default access to memories/documents/secrets; website labels plans honestly.
- Risks: premature enterprise claims, cloud coupling or privileged support backdoor.

## Current State

1. Demonstrated in branch-local automated tests: Space bootstrap/migration, scoped
   roles/invitations, email/domain proof rules, strict activation safeguards, recovery
   transactions and targeted tenant denials. Builds and bilingual mocked browser flows pass.
2. Implemented but not fully operationally validated: actual SMTP/DNS deployment,
   interactive supported-host recovery, provider/hardware lifecycle races and combined
   parallel-branch integration. No paid/cloud/hardware acceptance is implied.
3. Intentionally unavailable: multi-Space runtime, Business voice, guarded legacy
   proposals and this branch's absent knowledge API. No new unresolved final test
   failure is recorded; production readiness is not established.
4. Principal risks: migration collision, incomplete cross-agent knowledge/async
   isolation, trusted DNS/host assumptions and recovery backup lifecycle.
5. At restart, first inspect branch/worktree status, all agent handovers and migration
   union/applied histories. Preserve guards and unrelated changes before any integration.

## Recommended Next Steps

1. Resolve migration history and shared contracts with the other agents; establish a
   combined reproducible baseline without deploying.
2. Integrate knowledge/RAG through explicit identity boundaries and complete two-Space
   document/memory/job tests.
3. Complete worker/provider/stream lifecycle tests and independent isolation review;
   retain single-Space startup protection.
4. Validate SMTP/DNS and interactive recovery on isolated supported host deployments.
5. Implement reviewed Business voice principals and unified K-AI proposal authority
   before re-enabling currently guarded paths.

No feature, refactor, migration change, service restart or production deployment was
performed for this final handover. Development for this session ends with documentation.
