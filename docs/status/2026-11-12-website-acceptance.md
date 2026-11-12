# Current website acceptance — 2026-11-12

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
