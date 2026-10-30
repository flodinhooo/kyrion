# Kyrion Spaces — Agent 3 handoff

Branch: `feat/kyrion-spaces`.
Worktree: `E:/dev/Kyrion/kyrion/.worktrees/kyrion-spaces`.
Base: `2740399` on `refresh/product-credibility`.

The original worktree contained unrelated documentation/smoke-script edits and a
modified calendar recovery worktree. They were not copied, edited or committed.
No merge, deployment, publication, production migration or external messaging was
performed. Docker-backed tests used disposable PostgreSQL containers.

## Delivered

- Additive V37 Space schema, generated single-Space account membership, role scope
  foreign keys, immutable memberships and cross-Space role/invitation constraints.
- HOME/BUSINESS first-owner setup in the existing protected bootstrap transaction.
- Actor-derived Space metadata in `/v1/auth/me`, workspace header and Settings.
- OWNER settings and configurable non-OWNER default/custom roles.
- Hashed one-time/bounded invitations, metadata listing, expiry, revocation,
  current delegation checks and concurrent transactional redemption.
- Existing member/role management and OWNER/session protections retained.
- Local invitation fragment links and account creation in German/English.
- Process-local issuance limits and registration backoff using existing conventions.
- Minimal bilingual public product presentation; portal/support design documentation.

## Intentionally incomplete

Verified BUSINESS domain restrictions are unavailable: username-only identities
provide no verified email/domain proof. The UI says this explicitly. Domain
verification, policy rollout, recovery and their security tests remain required.

Multi-Space worker/stream/tool/provider isolation is not certified. Migration
rejects ambiguous legacy ownership and Core refuses multi-Space startup. No
multi-Space provisioning API is exposed. Device-provider coverage beyond the
tested Nanoleaf/catalog/command paths still needs a complete audit; gateway,
voice, discovery, background jobs, AI retrieval and restore paths require review
before lifting the single-Space guard. The current guard is an installation
boundary, not per-subsystem multi-tenant certification.

No cloud login, billing, subscription engine, installation registration, remote
invitation resolution, support grant, relay, tunnel or privileged support access
was implemented. The future contract and SUPPORT_OPERATOR rules are design only.

## Verification

Run from the dedicated worktree unless another directory is given. The default
machine Java was 22; Gradle initially could not find the required JDK 21. An ignored
local Microsoft JDK 21 archive was extracted under `.local-tools`; no build-file
toolchain requirement or committed dependency was changed.

```powershell
$env:JAVA_HOME=(Get-ChildItem .local-tools/jdk21 -Directory | Select-Object -First 1).FullName
& services/core/gradlew.bat -p services/core "-Porg.gradle.java.installations.paths=$env:JAVA_HOME" test bootJar --console=plain

# apps/web
pnpm install --offline --frozen-lockfile
pnpm exec next typegen
pnpm lint
pnpm exec tsc --noEmit
pnpm test
pnpm build

# repository root
pnpm install --offline --frozen-lockfile
pnpm --filter website lint
pnpm --filter website typecheck
pnpm --filter website build
pnpm --filter website test
pnpm --filter website exec playwright test --config playwright.spaces.config.ts
pnpm --filter website exec playwright test tests/spaces-product.spec.ts
pnpm --filter website exec prettier --check src/locales/en.json src/locales/de.json src/components/pages/product.tsx playwright.spaces.config.ts tests/spaces-web.flow.ts tests/spaces-product.spec.ts
git diff --check
```

Core: 244 tests across 47 suites, zero failures/errors/skips; `bootJar` passed.
Web: 170 tests across 52 files; lint, generated route types, TypeScript and build
passed. Website: 28 Playwright tests; lint, TypeScript and build passed. The
isolated Web browser suite passed four flows using a **mock Core**, not production
services. The public Spaces presentation test also passed independently after
moving it into its own file. Formatting passed for the changed website files.
No Kotlin formatter/linter is configured in the current Gradle build.

Initial failures were fixed: JSON defaults under the existing HTTP mapper,
PostgreSQL CASE timestamp typing, an invitation delegation test previously
allowing ADMIN to grant stronger USER rights, the extra Space setup audit event
in retention expectations, and browser locale assumptions. Existing compiler
deprecation warnings, Gradle 10 compatibility warnings, worktree root warnings,
and the existing standalone/`next start` warning remain non-fatal. One final
run failed while PostgreSQL Testcontainers initialization exceeded its startup
timeout; an unchanged retry passed all 244 tests with V37. No other containers
or running services were restarted or removed.

Security evidence includes concurrent first-owner bootstrap, V30/V34 upgrade
preservation, fail-closed ambiguous ownership, custom default roles, hashed codes,
expiry/revocation/replay/use limits, concurrent redemption, OWNER/escalation
denials, role/invitation scope, credential/device IDOR rejection, audit rollback,
calendar and personal-data separation, and the runtime multi-Space guard.
Verified domain enforcement and comprehensive provider/worker isolation are not
covered because they are not implemented.

## Files and integration

Core changes live in `security/SpaceService.kt`, existing security/authentication/
RBAC classes, V37, the authentication persistence integration suite and the
invitation limiter test. Web changes live in `features/spaces`, `/api/space`,
`/settings/space`, setup/auth proxies, shell/session metadata and invitation
navigation. Website changes are limited to product presentation, both locales
and isolated tests/configuration. The fixture server is
`infrastructure/spaces-ui-test-server.mjs`. Architecture/product boundaries are
documented in ADR 0031 and `docs/kyrion-spaces.md`; existing README/auth/RBAC docs
link or describe the new boundary.

Before integrating, reconcile V37 and ADR 0031 numbering with parallel agents and
review shared security, setup, shell, Settings, locale and integration-test changes.
Never modify an applied migration to resolve a collision. Preserve the compatibility
resource-owner UUID and credential/audit keys. The recommended next product slice
is verified email/domain ownership plus safe Business policy activation and local
OWNER recovery; multi-Space operation needs its own audited worker/stream rollout.

Concrete parallel conflicts observed before commit: the original worktree advanced
from `2740399` to `95a7540`, with uncommitted personal-context work modifying
`AuthenticatedRouteInterceptor.kt` and `Rbac.kt`, adding V35 personal-context and
V36 personal-knowledge migrations, and ADRs 0029?0030. This branch's unapplied
migration was renamed V37 and its ADR 0031 to avoid those collisions. These numbers
were validated in isolated test databases only. None of the original worktree's
concurrent changes was modified or incorporated. Reconcile the two shared security
files and repeat integrated tests against V35/V36/V37 together before integration.
