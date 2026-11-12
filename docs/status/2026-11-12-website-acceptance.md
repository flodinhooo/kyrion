# Current website acceptance — 2026-11-12

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
