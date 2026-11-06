# Unified identity handover

## Live Windows and Pi activation (latest checkpoint)

The owner subsequently authorized live rollout. Both personal installations are
now on **V46** with the reviewed Core JAR; Windows production Web and native ARM64
Pi Core/Web are running. Original databases/keys were independently restored and
verified before final target-bound apply. Existing accounts, Space, roles and
grants were verified unchanged after activation. No central links were created.

The migration tool needed a cross-JVM timezone normalization fix, reproduced with
a failing real PostgreSQL test and followed by **449 Core tests, zero errors,
one opt-in smoke skip**. Real production DE/EN browser checks passed on Windows
and Pi with normal TLS verification. Gateway/Voice are active with preserved
destinations; all three legacy bindings per installation still have zero grants.
Central login remains unconfigured/disabled, and physical/provider acceptance
and explicit binding review remain open. No password-authenticated production
owner journey or hardware action was claimed.

Full exact artifacts, protected backup locations, recovery boundaries and results:
[V46 live rollout](2026-11-06-v46-live-rollout.md). Older V39/V41/no-deployment
observations below are historical checkpoints, superseded by this execution.

## Redundant archive cleanup and personal runtime check

After retirement, the owner authorized removal of unnecessary archives. The full
checkout/build/dependency copies and redundant worktree Git metadata were removed.
Before deletion, all 530 historical `.run` files were moved into ignored
`.run/stabilization/identity-worktree-preservation/historical-runtime/`, recorded
in `historical-runtime-manifest.json` and verified against SHA-256 hashes.
Private environment/key copies and the independent complete Git bundles remain.
No private runtime data, branch ref, commit or Docker/database resource was deleted.
This supersedes the full-archive retention statement in the preceding checkpoint.

A read-only check of personal `kyrion-postgres` (`kyrion` database) found successful
Flyway history through **V39**, not current source V46. Canonical V40–V46 are still
pending there. Core `8080/actuator/health` returned HTTP200; Ollama11434, STT8040
and TTS8020 probes returned HTTP200. Web3000/login, Website3001 and AI8000/health
did not return successful responses within the bounded probes. These observations
are a runtime snapshot, not deployment acceptance or proof of current runtime
artifact identity. No personal migration, deployment or service restart occurred.

Source integration and isolated V1–V46 verification are complete; updating the
personal installation still requires the separate protected backup/independent
restore, target/artifact review, writer fence and rollout gates recorded in the
A/B closeout and schema runbook. Do not infer live readiness from current master.

## Worktree retirement after complete master integration

The owner requested that the integrated Identity checkouts no longer be needed
as worktrees. Both branches were rechecked as ancestors of master `170889c`, and
both checkouts still had clean tracked/untracked source. Their complete directory
trees, including private configuration, ignored files and caches, were moved
without deletion to ignored local archives:
`.run/stabilization/identity-worktree-archives/2026-11-06-closeout/identity-integration/`
and the sibling `unified-identity/`. Original Git worktree metadata was copied
alongside them; the archived `.git` pointers were renamed to
`.git.worktree-pointer.txt` so these are archives rather than active checkouts.

Only the two now-missing original registrations were pruned after inspecting the
dry run. `git worktree list` now contains only the primary master checkout. Both
branch refs and every commit remain intact. The verified final history bundle
also remains at `.run/final-integration/identity-master-final.bundle`.
No source/runtime configuration changed and no service or database was restarted.
The older retention statements below describe the preceding checkpoint; the
archives now replace those worktree directories. Deleting private archive data
or reclaiming its cache space is a separate retention decision.

## Master closeout after chats A/B (2026-11-06)

The owner explicitly authorized integration into primary `master` after the A/B
closeout. This supersedes older statements that master was not updated. Starting
HEAD was `b0932ab`, clean; both Identity worktrees had clean tracked/untracked
source at `dcc2dee` (integration) and `fe25b0d` (original feature).

- `3ea5179` merges the complete integration branch, preserving all later Calendar
  own-copy/time/dialog work and artifact-bound schema tooling from A/B.
- `4df369c` preserves original feature ancestry. Its source was already
  cherry-picked, reviewed and corrected in integration; no duplicate source or
  obsolete feature-only V44 is reintroduced.
- `73ee902` records final build isolation, cold-start acceptance assertions and
  the regression preventing a migration plan's approved target-version change.
- Both complete source histories belong to master. Worktrees and branch refs
  remain intact with private configurations and historical ignored evidence.
  No dirty or untracked source was discarded. A verified complete Git bundle is
  under ignored `.run/final-integration/identity-source-history.bundle`; private
  configuration copies and hashes are under ignored
  `.run/stabilization/identity-worktree-preservation/`. Originals remain in place.
  Credentials, caches and builds are not committed or copied over personal runtime
  configuration. Retained worktrees do not imply outstanding source integration.
- Calendar keeps ADR0039 and schema tooling ADR0040. Identity now uses ADR0041
  and the canonical-history decision ADR0042, with references updated.
- All master V1–V45 SQL and Identity V46 remain unchanged. Schema-only tooling
  retains default target45 and adds explicit `--target-version 46`; plans bind
  that choice. Only exact V1–V45 or V1–V46 catalogs are supported. Divergent old
  Identity V44 still fails validation without repair.
- Website supports an isolated `KYRION_BUILD_DIRECTORY`; full real-service
  acceptance uses independent Website/Web dev build directories.
- Personal services, databases and private runtime settings are not replaced.
  Live rollout, original-data restore and hardware/provider acceptance retain
  the separate gates in the A/B closeout.

Final verification and remaining work:
[master integration results](2026-11-06-identity-master-integration.md).

## Current integration — 2026-11-06

This section supersedes the earlier isolated-feature integration blockers below.
Primary `master` was clean at start at `fba7cbb`; other tasks subsequently
advanced it to `e3d9ff4`. This assignment does not update master. Work is on
**`integration/unified-identity`**, worktree
`E:/dev/Kyrion/kyrion/.worktrees/identity-integration`, based on that committed
master. Verified source inputs: Gateway `c398402` plus report `fba7cbb` (V42),
Calendar `69cee10` (V43), Identity `3884acf` plus `fe25b0d` (V44).
Identity was cherry-picked as `364bf15` and `3a01fab`. The single conflict was
the four historical expiry/due fixtures; master already fixes the same issue
with explicit year-2000 timestamps. Its corrected fixtures and Gateway call-site
adaptations were retained. No Calendar/Gateway feature or authorization check was
removed, and no foreign uncommitted change was adopted.
Later committed master changes were merged in `89fc2c6` (`ce10573`: disclosure
and Gateway rollout rehearsal) and `df42b1d` (`e3d9ff4`: household delivery).
`7c2b479` records the real-flow fixes, `92e66b7` the canonical migration decision,
and `3edca93` the final V1–V46 integration verification. The final handover commit
is discoverable from this file's Git history. All committed current master
features are retained.

### Integration fixes and migration evidence

- A real browser run found Core's `CentralOperationRequest` unnecessarily
  required primitive `confirm` even for poll/cancel under the current JSON
  runtime, returning `INVALID_REQUEST` to correct Web requests. Poll/cancel now
  use an operation-only DTO; completion uses a separate explicit confirmation
  DTO and rejects missing/null/false/string/numeric/container confirmation.
  A new actual MockMvc HTTP round-trip test reproduced the failure before the
  fix and verifies the complete/poll/cancel wire contract afterward.
- The account UI now waits for its authenticated link status before presenting
  connect/disconnect actions. This avoids replacing a premature connect form
  while a user is already entering the password on a linked account.
- Provider `iat`/`nbf` clock tolerance is bounded to 30 seconds, matching the
  explicit issue-time bound. A reproduced two-second-skew rejection is covered
  by a regression; future issuance beyond the bound and a token expired by only
  one second are rejected. Expiry and session lifetime are not extended.
- **Committed master's V1–V45 remain byte-for-byte unchanged.** The former
  feature Identity V44 conflicts with calendar V44 and becomes new additive
  **V46**, with identical SQL bytes. Its original V44 survives unchanged only
  as a historical test fixture outside active Flyway locations. See
  [ADR0040](../adr/0042-central-identity-canonical-migration-integration.md).
  `IdentityCombinedMigrationTest` verifies a fresh database applies exactly
  V1–V46 once; second normal migration is a no-op. Its representative upgrade
  seeds V41 with local OWNER/member, roles/grants, session, bootstrap state,
  integration ciphertext/nonce, legacy calendar and Gateway node/command;
  applies V42 without inventing command provenance; preserves explicit synthetic
  authority; applies V43 and creates joint event/participants; applies V44/V45
  and seeds personal disclosure plus destination/delivery metadata; then applies
  Identity V46. Complete row snapshots of sixteen existing tables and all prior
  checksums remain unchanged. A second startup validates and migrates zero rows.
  A third regression creates the old Identity-only V44 history and verifies
  canonical migration fails validation without repair or schema/data changes.
- The initial loaded Desktop run hit PostgreSQL startup timeouts. Only disposable
  Testcontainers database mounts now use tmpfs; all actual SQL/Flyway/HTTP tests
  remain enabled. Acceptance databases also use tmpfs. This is test-environment
  isolation, not a production persistence or durability change. An early new
  migration assertion was corrected to exclude Flyway's schema-creation marker
  (which has no migration version); failed runs are not acceptance evidence.

### Verification in the combined checkout

- **Core: 436 tests recorded, zero failures/errors, one opt-in standalone live
  test skipped**, `test bootJar` successful. Includes all Gateway/Household,
  authentication/RBAC/tenant suites, three new combined migration cases and
  thirteen identity integration tests. Provider transport is mocked only in the
  domain tests; real provider/browser acceptance is separate below.
- **Web: 241 tests / 66 files**, lint, typecheck and isolated production build
  passed. The new UI status gate is included in the final verification.
- **Website: 40 regular Playwright tests**, lint, typecheck and production build
  passed. Own new acceptance files pass targeted formatting; the historical
  repository-wide formatting backlog is unchanged.
- Gateway rollout-gate Python unit tests: **6 passed**, synthetic artifacts only;
  no operational rollout/restart command was executed.
- Full acceptance uses actual Website on 3119, Web on 3219, packaged Core on
  18092, Keycloak on 18089, Mailpit on 18025 and three independent real PostgreSQL
  databases. No route interception, fake provider, fabricated session or SQL
  session-expiry manipulation is used. Fresh central accounts are created in
  Keycloak's browser registration, email is delivered to Mailpit, and the email
  action returns safely to the website before existing-account reauthentication.
  The provider's actual profile→email→password setup flow and remembered-user
  password-only reauthentication are exercised.
- The full browser scenario passes with the canonical integrated services:
  registration/verified mail/website re-login, protected local setup and existing
  invitation signup, unmapped-central denial with unchanged user/role counts,
  explicit password/device-proof linking, successful central local login with
  unchanged permissions, actual short-token session expiry, actual provider
  stop/outage feedback, offline password login and password/checkbox unlink,
  preserved local member/OWNER access, logout and expired website session.
  Earlier selector/startup failures and the reproduced HTTP binding failure
  are excluded from successful acceptance; no temporary diagnostics remain.
  The final canonical run passed in **2.0 minutes**. The standalone opt-in JVM
  smoke remains skipped in the ordinary suite because its original 8089 fixture
  is separate; the packaged actual Core adapter is covered by this full 18089 run.

Reproduction: [full real-service acceptance](../../infrastructure/identity/FULL_ACCEPTANCE.md).
Core XML is retained in ignored `.run/stabilization/core-final-canonical-passed/`, browser results in the
worktree's ignored `apps/website/test-results`. Bootstrap/keys/passwords are
generated only into private ignored acceptance files. Existing personal services
and installation database were not migrated or restarted.
After acceptance, all five containers of the owned `kyrion-identity-full`
fixture were stopped. Their tmpfs synthetic databases are intentionally discarded;
private ignored configuration and original personal runtime data are preserved.

### Remaining integration and production boundaries

The parallel numbering collision was resolved against committed master, not by
editing another working tree: calendar retains V44/ADR0037 and V45/ADR0038;
Identity now uses V46/ADR0039, with ADR0040 recording the decision. No version gap
or duplicate remains. No production Identity V44 rollout was reported; the
historical feature branch and its commits remain intact. An installation that
actually applied the divergent Identity V44 is **still blocked** pending its own
reviewed compatibility plan and protected backup. Never repair checksums or
enable out-of-order migration to conceal this distinction. No such installation
or personal runtime was migrated here. Remaining dirty primary work is not adopted.

Production provider deployment, DNS, HTTPS/TLS, SMTP and registration/lifecycle
policy remain external configuration. The loopback HTTP/SMTP test environment
does not certify public infrastructure, mail delivery or a release rollout.
There are no installer changes, production deployment or primary-branch update.

### Concrete next slice: “invite Jennifer”

[The personal invitation implementation contract](../space-invitation-cloud-plan.md)
defines current code reuse, API bodies, identity/installation trust, minimum cloud
metadata, outbound mTLS polling, purpose-bound receipts, explicit consent,
local transaction/idempotency and offline/revocation races. No second invitation
system is implemented. The prerequisites are a trusted provider-owned immutable
cross-client account UUID (pairwise subjects cannot be guessed), explicitly
OWNER-approved per-installation keys/certificate and a narrowly scoped central
mailbox service. Existing local invitation policy remains authoritative.

The existing one-Space/password model imposes a deliberate gate: an existing
member can prove/link their local account without role changes; a new remote
recipient remains `LOCAL_ENROLLMENT_REQUIRED` until they can establish their
local password through the local Web. Portal acceptance alone must not upload
passwords, merge matching email accounts, assign OWNER or create a second Space
membership. This limitation and the new/existing/wrong-account, retry, expiry,
revocation and offline state matrix are explicit in the implementation contract.

## Historical initial feature delivery

Date: 2026-11-06. Source integration only; no merge, deployment, installer or
production database change.

## Source and architecture

- Branch: `feat/unified-identity`.
- Worktree: `E:/dev/Kyrion/kyrion/.worktrees/unified-identity`.
- Base: `fe5e65a` on primary `master`; the primary remains on `master`.
- Implementation commit: `3884acf83ef6406a9858ca5b6a51d3723f9bb30c`.
- Handover commit: discover with `git log -1 -- docs/agent-handoffs/unified-identity-handover.md`.
- Decision: [ADR 0037](../adr/0041-optional-central-identity.md).
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

| Area                        | Files                                                                                                                                                 |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Core identity               | `CentralIdentityProvider.kt`, `UnifiedIdentityService.kt`, `UnifiedIdentityController.kt`                                                             |
| Core persistence/dependency | V44 SQL and `services/core/build.gradle.kts`                                                                                                          |
| Core verification           | `UnifiedIdentityIntegrationTest.kt`, `CentralIdentityProviderTest.kt`, `CentralIdentityLiveTest.kt`, four existing authentication fixture corrections |
| Local Web                   | Central API proxy/tests, central contracts/messages/panel and existing login/setup/profile/Identity entry points                                      |
| Website                     | Account route/page, `src/lib/account/`, DE/EN resources/navigation, account schema/config and regular/live Playwright tests                           |
| Development                 | `infrastructure/identity/`, website browser helper and example environment files                                                                      |
| Documentation               | README, architecture/authentication guides, ADR0037, unified account guide and website/provider operations guides                                     |

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
