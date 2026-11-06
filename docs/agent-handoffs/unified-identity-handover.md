# Unified identity handover

Date: 2026-11-06. Source integration only; no merge, deployment, installer or
production database change.

## Source and architecture

- Branch: `feat/unified-identity`.
- Worktree: `E:/dev/Kyrion/kyrion/.worktrees/unified-identity`.
- Base: `fe5e65a` on primary `master`; the primary remains on `master`.
- Implementation commit: `3884acf83ef6406a9858ca5b6a51d3723f9bb30c`.
- Handover commit: discover with `git log -1 -- docs/agent-handoffs/unified-identity-handover.md`.
- Decision: [ADR 0037](../adr/0037-optional-central-identity.md).
- Operational/API guide: [central and local accounts](../unified-identity.md).

Existing Core has Argon2id passwords, opaque hashed sessions, host-secret
first-owner setup, bounded invitations, Business mailbox/domain policy and
host-local recovery. Space membership/roles are local and the single-Space guard
remains active. The website previously had no account support. No existing IdP
or public authentication service was found. Keycloak was selected from official
documentation for maintained self-hostable OIDC, PKCE, device grant and central
account management; no OAuth server was implemented.

The website now has an optional confidential OIDC relying party (openid-client,
RS256 signature verification explicitly enabled) and its own central PostgreSQL
session/flow store. Keycloak has a separate provider database. Local Core never
reads either central database; website never reads installation persistence.
This website-only BFF session boundary grants no platform/business permissions.

Changed implementation files are grouped as follows; `git show --stat 3884acf`
lists all 52 paths:

| Area | Files |
| --- | --- |
| Core identity | `CentralIdentityProvider.kt`, `UnifiedIdentityService.kt`, `UnifiedIdentityController.kt` |
| Core persistence/dependency | V44 SQL and `services/core/build.gradle.kts` |
| Core verification | `UnifiedIdentityIntegrationTest.kt`, `CentralIdentityProviderTest.kt`, `CentralIdentityLiveTest.kt`, four existing authentication fixture corrections |
| Local Web | Central API proxy/tests, central contracts/messages/panel and existing login/setup/profile/Identity entry points |
| Website | Account route/page, `src/lib/account/`, DE/EN resources/navigation, account schema/config and regular/live Playwright tests |
| Development | `infrastructure/identity/`, website browser helper and example environment files |
| Documentation | README, architecture/authentication guides, ADR0037, unified account guide and website/provider operations guides |

Local installs use a public RFC 8628 device client, outbound requests only, no
shared client secret or local callback. Nimbus OIDC validates the signed ID
token. Provider responses have a six-second full-body deadline and 128 KiB
streaming limit, including servers that stall after headers. Device grant has
no callback state/nonce/PKCE; website authorization code
uses all three (PKCE S256, state, nonce). ID tokens establish identity only, then
tokens are discarded and Core issues its normal opaque session. No tokens enter
browser storage/URLs or ordinary logs. Authorization-code callbacks necessarily
carry a short-lived protocol code; ingress must omit callback query strings.

## Model, migration and API

Additive **V44 `optional_central_identity`** creates:

- `central_identity_link`: local user FK/PK, issuer, subject, linked timestamp;
  `(issuer,subject)` unique. No email matching or user/role rewriting.
- `central_auth_session`: normal session FK/PK and linked-user FK; markers let
  unlink revoke central-created sessions without ending locally created ones.

Historical migrations and `auth_session` structure are unchanged. Transactions
use uniqueness plus advisory/workspace locking; mapping/session/audit commits
are atomic. Device codes stay only in bounded Core memory; random operation
handles bind LINK to the original local user/session and expire within ten
minutes. Operations are one-use; process restart abandons them. A future scaled
Core must route a pending operation to the originating process. Starts are
bounded to 30/minute/process and 256 pending operations; ingress limits remain
an operational responsibility. Failed local reauthentication uses bounded
backoff and safe security audit events.

Typed Core HTTP JSON under `/v1/auth/central`: `GET config/status`, `POST
start/poll/complete/cancel`, `DELETE link`. Status/link changes require local
authentication. LINK start and unlink require the local password; final linking
requires provider proof and explicit confirmation. Complete LOGIN returns the
existing Core session response. The same-origin Web proxy hides credentials in
HttpOnly cookies and checks CSRF, including anonymous device login.

Website endpoints: `POST /api/account/login`, `GET /api/account/callback`, `GET
/api/account/session`, `POST /api/account/logout`; exact configured callback,
no arbitrary return URL. Atomic PostgreSQL flow consumption prevents replay.

## Behaviour and security boundaries

- Local-only setup, login and authorized operations remain independent of the
  internet/provider. Local middleware never queries the cloud per request.
- Setup offers local-only or connect-after-protected-local-setup. New users
  still need local setup/invitation and a local password before linking; central
  proof alone cannot create a user, membership or OWNER.
- Existing users explicitly link after password and provider authentication.
  Only issuer/subject are imported. Keycloak leads those fields and its email;
  local username/password, memberships and all user content remain local.
- Pairwise subjects from different clients are not assumed equal. No global
  account-ID join, profile synchronization or password/hash copying exists.
- Unlink rechecks the password under lock, retains local login/OWNER access and
  revokes central-created local sessions. It can run with central login disabled.
- Central sessions expire within 15 minutes and no later than ID-token expiry
  (development provider normally gives five minutes). Reauthentication requires
  a new provider authorization; there is no offline refresh-token extension.
- Logout revokes the selected relying-party session. Central blocking prevents
  future proofs but an offline session can persist until bounded expiry. Local
  blocking/membership suspension remains locally enforced on each request.
  Unlinking is a separate operation. Global/backchannel logout is not implemented.
- No multi-Space operation was enabled; existing RBAC/tenant guards remain active.

Documentation conflict corrected: the old authentication guide claimed Strict
local session cookies, while the actual existing implementation uses Lax for
integration GET callbacks. This change documents that existing behaviour and
retains Strict separate CSRF/operation cookies; it does not change session policy.

## Configuration and local startup

See [isolated provider instructions](../../infrastructure/identity/README.md),
[website account operations](../../apps/website/ACCOUNT.md) and
`infrastructure/identity/core.env.example`. Accounts default disabled. Missing
disabled cloud configuration does not block local startup. Enabled Core settings
are validated; production requires exact HTTPS issuer, public client ID and no
loopback-development flag. Website additionally needs its confidential secret,
exact origin/callback and independent central database URL.

The isolated Compose project uses Keycloak 26.7.5 plus independent PostgreSQL
provider/website stores; loopback 8089/5549 only. Operator-supplied credentials
are ignored, never committed. Import has no users. Imported development realm
and HTTP settings must not be deployed as production configuration. Runtime
tests create disposable identities; manually verified test email is not SMTP
delivery evidence. Volumes/configuration survive stopping the test environment.

## Verification

- Core with existing JDK 21: `services/core/gradlew.bat test bootJar
  --console=plain` passed: **352 tests recorded, zero failures/errors, one
  intentional opt-in live-test skip**. Includes twelve new PostgreSQL identity
  tests: V41→V44 account/password/session/role preservation, local login without
  provider calls, explicit password/proof/confirmation, original-session binding,
  replay, unmapped-identity denial, concurrent link uniqueness, permission
  preservation, unlink/last-OWNER local access, logout/suspension and expiry while
  confirmation waits on an actual PostgreSQL lock. Existing full authentication,
  migration, RBAC and tenant suites passed. Provider transport is mocked in
  these domain integration tests.
- After the final full-body deadline fix, `test --tests
  '*CentralIdentityProviderTest' --tests '*CentralIdentityLiveTest' bootJar`
  passed **9/9, no skips** with `KYRION_IDENTITY_LIVE=true`. Eight synthetic
  real-HTTP/RSA tests cover valid proof, wrong signature/issuer/audience/expiry/
  authorized-party/subject/unsigned tokens, hostile discovery/verification URLs,
  disabled config, pending/slowdown/denial and a stalled response-body deadline.
  The ninth test calls the **actual Core Keycloak adapter against the real local
  Keycloak**, authorized by Chromium with a disposable provider user. That test
  writes only public user-code/verification-URI coordination to an ignored file;
  no device secret or token is written there.
- Local Web: **216 tests / 62 files**, `pnpm lint`, `next typegen` plus `tsc
  --noEmit`, and isolated production build passed. Chromium against that build
  and an HTTP-simulated Core exercised EN device login, HttpOnly operation and
  session cookies, absence of operation secret in DOM, explicit linking,
  password/checkbox unlinking, and DE labels. This browser run does not pretend
  to be a real Core/IdP run.
- Website: **40/40 regular Playwright tests** passed, including twelve new
  security/browser cases. Actual openid-client against a synthetic RSA OIDC
  issuer rejects wrong signature, issuer, audience, state, nonce, expiration and
  algorithm, and verifies PKCE S256. Lint, typecheck and production build passed.
- Opt-in website suite against **real local Keycloak/PostgreSQL: 3/3 passed**:
  browser authorization code login/session, CSRF logout/replay rejection,
  central-account suspension with existing-session bounded window/new-login
  denial, public device grant with explicit browser confirmation, concurrent
  eight-way atomic flow consumption and distinct subject/account handling.
- Changed website files pass targeted Prettier checks. Repository-wide website
  `format:check` still flags **49 untouched baseline files**; no broad formatting
  was performed. Core has no separate configured formatter/linter task; Kotlin
  compilation and test/build checks ran. `git diff --check` passed.
- Initial full Core failures were three existing fixtures assuming Docker SQL
  time minus one second was expired according to the JVM clock. A read-only
  measurement showed the Docker clock approximately 0.7 seconds ahead, varying
  under load. Four test fixture updates now bind explicit JVM timestamps; no
  production clock or authentication behaviour was changed. The complete rerun
  passed. Disposable PostgreSQL initialization uses `--no-sync` only in the new
  test fixture to avoid slow Desktop fsync startup; production is unchanged.
- Initial Java live smoke rejected Keycloak `slow_down`: the production service
  already increases polling intervals correctly; its standalone opt-in test was
  fixed to do the same. The IDE debugger could not create a run configuration for
  the ignored linked checkout; temporary sanitized error-class/code diagnostics
  identified the result and were removed before final passing checks.

Full-suite XML is preserved in ignored
`.run/stabilization/core-full-test-results/`, final adapter/live XML in
`.run/stabilization/core-identity-live-test-results/`. Local UI browser artifacts
are ignored under `.run/browser-review/unified-local-identity.*`. The ordinary
test suite explicitly disables central website accounts. Production DNS/TLS,
SMTP, external provider hosting and hardware acceptance were not exercised.
The complete local Web→Core→Keycloak chain was verified in component/integration
layers rather than one entirely unmocked browser deployment.
The three isolated development-provider containers were stopped after acceptance;
their private ignored configuration and volumes remain available for reproduction.
Existing application/runtime services were not restarted or replaced.

## Parallel work and integration

Primary uncommitted Gateway authority and household-calendar changes were
identified at start, including V42/V43 and ADR 0036. None was copied, stashed,
reset, merged or rebased. This branch reserves V44/ADR0037 and leaves existing
Auth/RBAC/Spaces contracts intact, adding standalone central identity contracts.
No changes to `packages/api-contracts` or installer files were needed.

At final inspection, the parallel Gateway stream also modifies
`AuthenticationPersistenceIntegrationTest.kt` around command-authority assertions.
This branch changes four expiry/due fixtures in other hunks of that file. Review
both changes together during integration; neither parallel change was copied.

**Before any installation:** integrate the eventual canonical Gateway/calendar
V42/V43 source commits with V44, inspect any new migration-number collisions and
rerun the combined Core/Web suites. V41→V44 checks here intentionally exclude
uncommitted foreign migrations. Installing this branch's V44 first and later
introducing lower migrations is an out-of-order hazard, not an approved upgrade.
Do not repair checksums or enable out-of-order migrations to conceal it.

Review the commit on its branch, integrate into an owner-selected integration
checkout without overwriting dirty `master`, then verify combined history and
rehearse on an isolated restored database. No merge or deployment was performed.
Keep this linked worktree until integration; private ignored development config
is not part of the source commit.

## External setup, installer interface and prioritized follow-up

1. **Before production:** deploy/harden/back up Keycloak and central PostgreSQL,
   provision reviewed HTTPS/DNS, exact website redirect/client secret, public
   device-client policy, central registration/email delivery and ingress limits.
   `auth.kyrion.ch` remains proposed configuration, not existing infrastructure.
2. **Before integration/rollout:** reconcile V42/V43 and reverify the combined
   migration/authorization suite; rehearse backup restore with original keys.
   Complete production reverse-proxy cookie, callback-log and TLS acceptance.
   Include one fully unmocked Web→Core→Keycloak browser run in that deployment
   rehearsal; the component-level evidence above does not replace it.
3. **Later installer:** expose optional enabled/issuer/public-client-ID fields,
   default local-only, preserve host-secret first-owner setup, provide the
   connect-after-setup UI path and preserve offline credentials/recovery. Never
   distribute the website secret, require cloud setup, register arbitrary LAN
   callbacks or infer local privileges. Installer itself is unchanged.
4. **Optional hardening:** central backchannel/global logout and distributed
   rate limits/session housekeeping; version future website schema migrations;
   passkeys and cross-client central-account services only for a concrete need.
