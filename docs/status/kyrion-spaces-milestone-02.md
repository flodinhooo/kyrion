# Kyrion Spaces Milestone 02 — Agent 3 handoff

Branch: `feat/kyrion-spaces`; worktree:
`E:/dev/Kyrion/kyrion/.worktrees/kyrion-spaces`.
Base: Milestone 01 commit `9740b88cdce710e37012ecf482c39876b37bcacf`.
No merge, cherry-pick, deployment, publication, production database operation or
external user message was performed. The original worktree was inspected read-only;
its concurrent edits were not incorporated or overwritten.

## Implemented foundations

- Pending and SMTP-verified email identities, separated replacement-address state,
  random hashed 15-minute one-use challenges, resend limits and transactional proof.
- Enumeration-safe public invitation email requests and account-creation proof bound
  to recipient, invitation and Space. Existing unbound OFF-policy registration works.
- OWNER-only exact-domain allowlist, IDNA normalization, DNS TXT challenges,
  expiration/rotation, 30-day evidence validity and immediate evidence invalidation.
- Strict policy requires configured SMTP, current domain evidence, verified allowed
  addresses for every enabled member and provisioned local recovery. Activation
  revokes outstanding invitations with explicit confirmation and prevents lockouts.
- Current members retain access after DNS expiry; new enrollment/email changes and
  reactivation fail closed. OWNER can disable policy without current DNS evidence.
- Explicit local attestation with host key/current OWNER password and audit; it does
  not count as SMTP verification or enable strict policy.
- Interactive host-only recovery: installation/Space-bound host key plus offline
  code, five-minute session, replay protection, password/code rotation, session/proof/
  invitation revocation and sealed audit. No new OWNER, HTTP recovery or login token.
- CLI verifies the existing audit chain before writing. POSIX modes and Windows ACLs
  protect host material; redirected execution is rejected. Recovery sessions can
  expire without stranding the replacement offline code. Authenticated local code
  rotation supports maintenance before yearly expiry.
- Central actor/Space authorization in RBAC/authentication, role scope joins, nested
  room/device/node/command/satellite/session database constraints, active-worker
  checks, scoped pending voice actions and playback acknowledgements.
- K-AI stream preflight/event/session checks; current policy revalidation before
  provider invocation; no charge for a reservation rejected before invocation.
- Bilingual identity/DNS/policy/recovery UI, signup email proof, guarded browser
  voice and direct Web synthesis. Public product wording remains prototype-scoped.

## Deliberately guarded and incomplete

Multi-Space startup remains blocked. Business satellite/browser voice and direct
Web synthesis remain disabled because there is no reviewed per-person satellite
principal model. Legacy proposals are disabled for Business and HOME with explicit
K-AI policy, since their old endpoint bypasses routing/budget authority. Typed manual
device control remains available. No cloud escalation was introduced.

The knowledge/RAG/document/vector implementation is changing in the other worktree
and absent here. Its API is tested as 404. It is not certified by these tests.
Provider-specific race cases, all gateway polling/retry/cache lifecycles, managed
service-to-service isolation and every long-lived stream are not exhaustively
validated. [Audit matrix](../spaces-tenant-audit.md) records exact paths, evidence,
missing tests and the tested `TenantBoundary.personal/shared/actor` integration
boundary. No complete tenant-isolation claim is made.

Actual customer SMTP/DNS, physical hardware, interactive Linux/Docker production
operator acceptance and combined parallel-branch migrations remain deployment
checks. SMTP tests include a real loopback relay without STARTTLS; it cannot
receive AUTH or message data. DNS tests use a real loopback UDP TXT response,
including split character strings. Business service integration tests replace
delivery/DNS with deterministic fixtures; no real mailbox/domain was contacted.
DNS trusts the operator's resolver/network and does not validate DNSSEC itself.

## Migration and parallel integration

V38 `business_identity_and_local_recovery` is additive; no account, role, resource,
credential ciphertext/key or historical audit row is rewritten. Existing identities
are not auto-verified, policies remain OFF and old invitations are unchanged until
an explicit policy/recovery action. Invalid nested ownership aborts with
`TENANT_NESTED_OWNERSHIP_INVALID`. Migration preservation runs against real PostgreSQL.
ADR 0032 records the design before implementation.

The committed Spaces V37 was **not** renumbered. The other worktree has a conflicting
`V37__personal_calendar_context_opt_in.sql` alongside V35/V36 knowledge/context work.
That collision must be resolved explicitly before integration, preserving applied
history. The last observed main-worktree commit was
`082b661841a5e9558af200051314ebbe50fb7a86`; its uncommitted context/knowledge/AI/Web/
Compose edits were not copied. Shared conflict points include RBAC, interceptor,
authentication persistence tests, Core build, K-AI orchestration/settings/stream
controller, Web shell/chat and context interfaces. Preserve both features' grants
and guards when resolving conflicts; run combined migration and two-Space tests.

The sole application dependency added is Spring Mail via the existing Boot BOM.
Core's main class is explicitly pinned so the separate administrative entry point
does not change normal boot behavior. SMTP and DNS configuration lives in isolated
identity resources; existing installer/Compose/Docker templates were not modified.

## Validation commands and final results

Core: **266 passed, 51 suites, zero failures/errors/skips**, including **66 real
PostgreSQL integration tests**. Web: **186 passed, 55 files**. Website: **28 passed**.
Local Web browser suite: **6 passed with mock Core**. Lint, TypeScript and both
production builds passed. Core `bootJar` passed. ktfmt 0.54 Kotlin-language style
formatted/checked the ten new Kotlin files; existing files retain focused edits.
The formatter/JDK are ignored local tools, not new application dependencies.

From the dedicated worktree:

```powershell
$env:JAVA_HOME=(Get-ChildItem .local-tools/jdk21 -Directory | Select-Object -First 1).FullName
& services/core/gradlew.bat -p services/core "-Porg.gradle.java.installations.paths=$env:JAVA_HOME" test bootJar --console=plain
& services/core/gradlew.bat -p services/core "-Porg.gradle.java.installations.paths=$env:JAVA_HOME" test --tests dev.kyrion.core.security.IdentityTransportTest --console=plain

# Before commit, $newKotlinFiles was populated with git ls-files --others --exclude-standard.
# After integration, use added *.kt paths from the Milestone 02 diff instead.
& "$env:JAVA_HOME/bin/java.exe" -jar .local-tools/ktfmt-0.54.jar --kotlinlang-style @newKotlinFiles
& "$env:JAVA_HOME/bin/java.exe" -jar .local-tools/ktfmt-0.54.jar --kotlinlang-style --dry-run --set-exit-if-changed @newKotlinFiles

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

The packaged CLI smoke command used quoted `"-Dloader.main=..."` on PowerShell;
redirected execution exited 1 with `Interactive host console required` as intended,
before database connection or any administrative operation. An initial unquoted
PowerShell argument did not reach the CLI; the supported Windows command is quoted
in [the procedure](../business-identity-and-recovery.md).

Regression fixes during validation included the separate-main-class boot selection,
existing test-double compatibility, DNS split-TXT parsing, translation alignment,
and JVM/database clock skew in immediate domain invalidation/reactivation. Expiry
checks now use the same injected authority clock there. Existing compiler/Gradle
deprecation, worktree-root and standalone test-server warnings remain non-fatal.

## Next milestone

Integrate the parallel knowledge/context work through explicit actor/Space contracts
and add the missing document/blob/chunk/vector/embedding-job/source-stream tests.
Introduce least-privilege Business satellite principals and route every proposal/
speech path through Core policy and accounting before re-enabling voice. Complete
provider/worker/stream lifecycle tests and independent review before considering
removal of the single-Space guard. Portal and SUPPORT_OPERATOR remain design only:
customer-initiated, scoped, temporary, revocable and audited, with no global OWNER.
