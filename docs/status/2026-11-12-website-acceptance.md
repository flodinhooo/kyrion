# Current website acceptance — 2026-11-12

Latest customer-account scope: browser self-registration and remembered website sessions supersede the earlier invitation-only/short-session checkpoints. See the customer-account redesign section at the end and [ADR 0051](../adr/0051-customer-website-accounts.md). Local Core link/session rules are unchanged.

Latest result: **KY-020 completed; publication verified. KY-021 remains blocked by deployed contact-origin configuration.** The original audit below describes pre-publication observations; the post-deployment section supersedes its deployment-open and old-public-copy statements. KY-022?KY-024 remain open.

This is the current website acceptance record. The [active backlog](TODO.md)
remains the single work order; KY-020–KY-024 identify the open website gates.
The [detailed website audit](../../apps/website/STATUS.md) records source,
verification, cleanup and the limits of production access.

## Decision

**Integrated source and isolated software verification: accepted within the
recorded scope. Complete production acceptance: open.** No audit/build result
authorizes mail delivery, account mutation, production deployment, database
migration or installation/device control. The concurrent native installer work
is outside this website/documentation acceptance.

The public informational website responds successfully. The public account API
is enabled and the HTTPS identity discovery works. Those observations supersede
the old blanket statements that identity is only loopback or that the website
account feature is disabled. They do not establish a completed user journey.

## Evidence

| Layer                        | Accepted observation                                                                                                                                                                                                                                     | Limit                                                                                                                                                               |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local integration            | Website functional source was present in local master and the checked GitHub master baseline; no extra worktree or unmerged local branch was found. Audit fixes are committed locally in `f715000`, with this documentation/privacy follow-up afterward. | Local integration is separate from a push, Vercel deployment and productive verification.                                                                           |
| Software                     | The audited Website passed 46 isolated Playwright tests, ESLint, formatting, strict TypeScript and production build. The follow-up rechecks the localized privacy link and retention/cookie explanation in the browser.                                  | Ordinary tests disable real SMTP and production account access. They do not prove delivery or real registration/reset/login.                                        |
| Cleanup                      | Seven obsolete `.next-*` trees removed; 182,128,160 ordinary-file bytes freed. Only current `.next` remains. Dependency junctions were removed without following targets; dependencies and private configuration preserved.                              | `node_modules`, current build and tracked identity tests are intentionally retained. Excluded folder coloring is not missing integration.                           |
| Public final host            | HTTPS apex requests ended on `https://www.kyrion.ch/` with HTTP200.                                                                                                                                                                                      | The public response still contained the older apex canonical metadata. Local canonical/OG/robots/sitemap/template corrections await publication.                    |
| Public privacy               | `/privacy` and `/en/privacy` both returned HTTP200; neither public body contained the new HttpOnly explanation during the recheck.                                                                                                                       | Existence of a page is not evidence that the audited correction is deployed or legally/operationally reviewed.                                                      |
| Public account               | Anonymous `GET https://www.kyrion.ch/api/account/session` returned HTTP200 and enabled=true.                                                                                                                                                             | No authenticated session, callback, registration, verification/reset mail, logout or expiry journey was exercised.                                                  |
| Identity transport           | HTTPS discovery returned HTTP200 with issuer `https://auth.kyrion.ch/realms/kyrion`.                                                                                                                                                                     | No current administrator configuration, DNSSEC state, real-account lifecycle or installation opt-in was certified.                                                  |
| Central SMTP/storage history | [Later central SMTP](../agent-handoffs/2026-11-07-central-identity-tunnel.md) and [dedicated Neon provisioning](../agent-handoffs/2026-11-07-neon-website-sessions.md) have dated evidence.                                                              | Central identity mail is distinct from Vercel contact mail. Database provisioning and a local private env file do not certify current Vercel runtime configuration. |

The repeated public checks were GET-only, anonymous and performed without
reading or printing secrets. Existing private files, productive settings,
accounts, mailboxes and databases were not modified. No test mail was sent.

## Corrections included in the reviewed source

- Canonical metadata, Open Graph URLs, sitemap, robots and contact-origin
  template agree on the final `www` host. An apex contact-origin setting would
  reject a submission from the redirected `www` page.
- DE/EN privacy copy describes website session/flow HttpOnly cookies, central
  provider cookies, separate website session storage and the distinction between
  session validity and deletion/retention of stored records or backups.
- Contact forms link directly to the privacy page in the selected language.
- Root README, current status, continuation context, identity/account/contact
  instructions and the detailed website status now point to this acceptance and
  the same backlog IDs. Historical/archived findings retain their dates and
  evidence boundaries; they are not silently rewritten as fresh acceptance.

## Open gates and explicit completion evidence

| ID                       | What remains                             | Required evidence                                                                                                                                                                                                                                                 |
| ------------------------ | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| KY-020                   | Publish the reviewed website corrections | Record the deployment source; verify final-host metadata and both-language public privacy text after deployment. Current Vercel deployment identity/settings are not authenticated in this audit.                                                                 |
| KY-021                   | Accept actual website contact mail       | Privately verify all seven Production variables, including the exact final origin, then perform an authorized owner test with inbox/spam, Reply-To and safe failure observations. Do not infer success from source tests or Pi SMTP.                              |
| KY-022 / KY-003          | Accept public website account journeys   | Authorized account/browser evidence for registration availability, verification/reset mail, callback, persisted session, logout and expiry. Preserve the independent local Core account/link permission boundary.                                                 |
| KY-023 / KY-006 / KY-015 | Offer actual installer artifacts         | Pass publication/signing/platform/distribution gates, then populate the catalog from verified published assets and check actual downloads. The current website catalog is empty.                                                                                  |
| KY-024                   | Accept deployed abuse/privacy operations | Verify shared/platform request limits and operational provider/retention/deletion/mailbox procedures. Source has an abuse extension point but no distributed limiter; deployed platform rules are not visible here. Factual privacy copy is not a legal sign-off. |

Full documentation search/history, wider Business features and other planned
product slices remain planned. They are not unfinished merges inside old
generated Website build directories. Current installer/native Windows changes
require their own tests, integration and target acceptance.

## Verification record

Source baseline before this follow-up: `f715000`. Website lint, formatting,
typecheck, production build and the full isolated suite were rerun after the
follow-up's UI/resource changes. See the recorded final results in
[website status](../../apps/website/STATUS.md#final-verification).
Relative documentation links and the new backlog IDs are checked together so
the README, TODO and acceptance cannot silently point to different current work.

## Post-deployment verification

On 2026-11-12 the owner explicitly authorized pushing the complete committed
master history, including the intervening installer/Home Assistant commits.
Uncommitted native-installer changes were excluded. GitHub master advanced to
`48d064a35f3e4d616831d84ba8669d9548625cc3`. The Vercel status for that commit
reported success: [deployment](https://vercel.com/florianrogenmosers-projects/kyrion-website/HnhW3DTy9NGW1EECxUJ4bV9XiWvR).

- Public Home, EN Home, both Privacy and Contact pages, Download, account session,
  robots and sitemap returned HTTP 200. Apex redirects to the final www host.
- Canonical, robots and sitemap use `https://www.kyrion.ch`. Both privacy pages
  contain HttpOnly and record-retention explanations; contact pages expose their
  localized privacy links. This closes KY-020 for the audited corrections.
- Anonymous account session reports enabled=true, session=null and no-store.
  Identity discovery returned HTTP 200 with a browser User-Agent; one plain
  urllib request returned 403. Real browser/account lifecycle remains untested.
- Empty JSON contact probes cannot pass validation or send mail. With the exact
  final www Origin they returned HTTP 403 `CONTACT_REJECTED`; with the old apex
  Origin they reached validation and returned HTTP 400 `CONTACT_INVALID`.
  Together with the reviewed handler this identifies an old allowed Origin in
  production. Set Production `CONTACT_FORM_ORIGIN=https://www.kyrion.ch` and
  redeploy. No authenticated Vercel settings tool or CLI is available here.
- No real inquiries, account creation/reset mail, authenticated sessions or
  database changes were exercised. SMTP values and mailbox receipt remain
  unverified; no secret value was read or printed.

### Owner input still required

1. Vercel project access, or an owner change of the Production contact Origin
   followed by redeployment. Confirm the six server-only SMTP/recipient variables
   privately; do not paste credentials into chat. Access is also needed to review
   deployed contact request limits (KY-021/KY-024).
2. After configuration is corrected, an approved test mailbox/account and owner
   participation to confirm inquiry receipt/Reply-To, verification/reset delivery,
   sign-in/logout and expiry (KY-021/KY-022). Passwords need not be shared.
3. Operational decisions for inquiry/account/security-record and backup retention,
   deletion and provider responsibilities (KY-024). Factual text is published;
   operational/legal acceptance is separate.
4. Installer release acceptance/signing/publication evidence (KY-023, linked to
   KY-006/KY-015). An empty catalog remains intentional; no arbitrary build is
   published as an accepted release.

The repository-wide GitHub Actions run is separate from the successful Vercel
build and the 46 locally passing website tests. Its status is available in the
[push CI run](https://github.com/flodinhooo/kyrion/actions/runs/43254630035).

Push CI observation: **Public website checks passed**, as did Web checks and all
three native installer build jobs. Installer validation on Ubuntu failed with
three errors and one failure, all involving `E_STAGING_PERMISSIONS` in provision
tests; the Windows matrix partner was cancelled. Core/fresh-stack jobs were
still running at that observation. This separate installer defect needs
investigation in the ongoing installer work; no owner credential or decision
is needed to diagnose it. No full-repository green-CI claim is made.

## Website client activation, 2026-11-12

The owner subsequently reported Keycloak's "Client disabled" page and explicitly
authorized checking private administration and activating the website client.
Existing host-key-verified SSH access to the Pi and the loopback-only Admin REST
API worked. The existing `kyrion-website` client had the exact www callback and
origin, confidential client authentication, authorization code flow, S256 PKCE
and RS256; implicit and direct password grants were disabled. Only `enabled`
changed from false to true. Registration remains closed and verified-email
policy unchanged; no users, passwords, roles, client secrets or local Core flags
were changed. No service restart or website deployment was required.

A private mode-0600 client snapshot and operation evidence were retained on the
Pi under its existing identity directory. Activation timestamp:
`20261112T164256Z`; correlation ID:
`0e55ed0d-373a-41c7-a0a6-1447668c5624`. Scoped rollback is to disable this client
again without deleting users or restoring a stale database.

An actual anonymous Production website login POST redirected to auth.kyrion.ch
and returned HTTP 200 with username/password fields and no disabled-client error.
The website issued its browser flow cookie. No credentials were entered; this
proves login initiation, not authenticated callback, user existence, verified
email, session issuance, reset or logout. KY-022 remains open for those journeys.
The owner also supplied a screenshot of successful contact submission after
correcting Vercel; mailbox receipt and Reply-To are still unconfirmed. Earlier
contact-origin rejection evidence above is historical after that correction.

## Invited account onboarding follow-up

The owner explicitly requested a personal central account, supplied their chosen
email privately and authorized a setup invitation. A regular enabled user was
created with emailVerified=false, no operator-assigned password and required
VERIFY_EMAIL/UPDATE_PASSWORD actions. Keycloak accepted one setup-email request
(HTTP 204), with a 30-minute action-link lifespan. This does not establish inbox
receipt, completed verification/password setup, authenticated callback or local
linking. Account identifiers and operational evidence remain private on the Pi;
no personal email, password or invitation URL is stored in this document.

The Website now explains central versus local credentials, the invitation-only
private test phase, and the three local connection steps in DE/EN. Invitation
requests lead to localized Contact; the signed-in state keeps the connection
instructions but hides the invitation request. Public self-registration remains
closed. No local account is inferred from email or website login.

Verification after these UI changes: lint, formatting, strict types, production
build and all 47 isolated Playwright tests passed (28.6 seconds). The added browser
coverage checks DE/EN anonymous and signed-in onboarding states, the three steps
and the localized invitation-request destination.

The requested Windows installation was checked before local activation: its Core
was not listening on 8080 and Docker's Linux engine was unavailable. Port 3000
belonged to the owner's Portfolio application and was preserved. Existing
private infrastructure configuration was backed up and optional central login
prepared with the exact HTTPS issuer and public `kyrion-local` client, with
loopback HTTP disabled. Provider-side local device grant is already enabled,
public and has direct password grants disabled. Docker Desktop startup was
attempted, but its readiness command did not return; no WSL shutdown, database
reset/migration, firewall change or automatic account link was performed. Local
runtime availability and the owner's password-confirmed link remain pending.

### Subsequent Windows runtime and setup verification

The owner's central setup was read back privately: enabled=true,
emailVerified=true, password credential present and no remaining required
actions. No password value was read. This supersedes the pending-setup state.
The guided website was deployed in `dba175e`; Vercel reported success and the
public German account page contained the new connection guide.

Docker subsequently became ready and PostgreSQL completed crash recovery.
Read-only validation found 46 installed migrations, no mismatches, no pending
migrations and no active sync leases. The hash-verified, previously accepted V46
Core artifact was started on loopback with the prepared optional central-login
configuration. Health returned UP and central config returned enabled=true.
The current local web app started on `http://localhost:3002`, preserving the
Portfolio listener on 3000. Both its login page (HTTP 200) and forwarded central
config (HTTP 200, enabled=true) were verified. The actual local link still
requires the owner's local-password proof, central code authorization and
explicit confirmation; none of those proofs was bypassed.

The owner then reported npm predev failing because the local recovery helper
could not start. Its unconditional Windows ACL operation was re-propagating
permissions across the large recovery directory, exceeding the command timeout.
Startup now first checks owner-only, protected full-control ACLs and skips the
mutation when they already match. Missing/inadequate protection still requires
the native ACL operation and a successful recheck; checks do not accept inherited
or additional read grants. The operator key remains private. Actual Node 22
helper startup and the exact `npm run predev` path passed. Nine recovery tests,
including native Windows ACL acceptance/rejection, and JavaScript syntax passed.
No unrelated installer source, Portfolio process, schema or local-user data was
changed. These runtime checks supersede the earlier startup-blocked observation.

## Customer-account redesign

Owner requested direct customer registration, a header account menu and continued
sign-in instead of the 15-minute status screen. ADR 0051 records the website-only
change before implementation. The header now shares account state across pages,
with account overview, provider account settings and logout when signed in.
The account page shows customer actions; local link instructions are collapsed.
Anonymous users can choose Create account or Sign in directly. The same-origin
registration POST uses standard OIDC prompt=create with PKCE/state/nonce and the
existing exact callback. No password or provider-admin credential enters the UI.

New website sessions have an opaque persistent Secure HttpOnly cookie and an
absolute 30-day deadline. Short signed proofs are renewed on demand server-side;
proof caching is capped at five minutes. Refresh credentials are AES-GCM encrypted
with a domain-separated key from the server-only client secret and session digest
binding. The dedicated database locks a session row while renewing so parallel
requests and logout serialize. Invalid/revoked/changed identity is denied;
transient provider failures preserve retry without granting access. Local logout
works without renewal and removes the row before best-effort provider revocation.
No offline token grant, sliding absolute deadline or local Core lifetime change.

The dedicated central Neon database was confirmed to contain website tables and
no Core Flyway history. Additive migration 002 was applied over certificate-verified
TLS: nullable renewal columns and UPDATE permission only on those columns.
No local or provider database schema was changed. Old sessions retain their
original short expiry and need one fresh sign-in for the remembered behavior.

Provider configuration was privately snapshotted and scoped changes applied:
registration and email-as-username enabled, verified-email and brute-force
protection preserved, password recovery enabled, optional first/last name,
minimum 12-character policy when no prior policy existed, and online SSO/website
session idle/max bounded to 30 days. Access-token lifetime was not increased.
Operation correlation: `13b933d8-5378-4535-831a-dfbaf394a9be`.
The public provider registration entry returned HTTP 200 with email fields;
the required Password Validation execution is enabled. Keycloak's email-first
registration intentionally requests the password after mailbox verification.
No test registration was submitted and no unsolicited account/mail was created.

Verification: full suite including actual disposable PostgreSQL passed all 50
tests (15.2 seconds). The ordinary production-disabled suite passed 49 with the
explicit disposable-DB test skipped. Native SQL tests cover least-privilege
column grants, encrypted credentials, concurrent renewal/logout, revoked/changed
identity, transient retry and absolute expiry. Signed synthetic OIDC tests cover
initial and refreshed proofs, including unverified-email denial. Desktop/mobile
browser checks cover the customer menu, registration forms, shared logout state
and responsive navigation. Visual review found and corrected a left-clipped
mobile dropdown, adding explicit viewport-bounds regression coverage.
Lint, formatting, strict types and production build pass. DE/EN privacy copy now
explains persistent cookies and encrypted renewal records; expiry is not a data
retention promise. Live authenticated renewal, new customer mailbox completion
and operational privacy/abuse review remain KY-022/KY-024 acceptance rather than
claims derived from local fixtures.

## Visible code-linking follow-up

The owner clarified that the local linking entry must be prominent and its code
must be entered on the website. ADR 0052 records this user flow before changes.
The local Profile now starts with its own Link account section and navigation
item; the avatar targets that section. The code is large and has Copy/Open
website actions. Official-provider operations open the website's localized
account code-entry tab. Provider approval automatically completes LINK through
Core's unchanged session-bound, one-use completion endpoint. Password proof,
provider validation, expiry, identity uniqueness, permissions and audit remain.

The website account menu and account navigation now expose Link account with a
real code form. Same-origin/session/CSRF checks precede a fixed-issuer device
verification redirect. Invalid codes produce localized errors. No webhook,
local callback host, general relay, installation DB access or automatic email
matching is introduced. The website does not assert link success from entry.
German labels are stored as Unicode source; the earlier lossy shell-generated
question marks were corrected in the preceding redesign. Fresh browser loading
is required for already-open old application bundles.

Verification: Website lint, strict types and production build passed; 50 regular
Website tests passed with the opt-in disposable-DB test intentionally skipped.
Local Web lint, strict types, 277 unit tests and production build passed. The
real isolated Keycloak/Mailpit/PostgreSQL/Core/Website/Web acceptance passed
(1 test, 2.0 minutes), including real registration/mail verification, website
code entry, automatic local LINK, unchanged Space rights, central local-login
expiry, provider outage/local password login, unlink and remembered website
session across reload/short proof expiry, then website logout. The initial
cold provider startup exceeded its readiness window; the rerun used the same
isolated stack after readiness. An old final assertion expecting website expiry
was updated to verify the requested remembered behavior. Test service containers
were stopped afterward; personal Windows/Pi services and data were preserved.
Generated test-only tsconfig additions were compared structurally and restored.
Historical earlier counts retain their scope.
