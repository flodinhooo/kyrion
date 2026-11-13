# Website integration and readiness audit

**Current publication, 2026-11-13:** `eb07775` is deployed successfully. Live DE/EN
field correction, mobile layout, runtime-error and API-boundary checks passed.
The owner confirmed personal login/local linking and installation display. Contact
Origin is resolved. [Current acceptance](../../docs/status/2026-11-13-website-acceptance.md)
lists remaining receipt, lifecycle, operational and release gates. Earlier sections
below retain their dated scope; their old blockers are superseded.

**Linked-installation follow-up, 2026-11-12:** account overview lists confirmed
installation/Space labels and local usernames; `/connect` is the dedicated code
entry. Local Profile displays verified central email/name. The real isolated
registration/link/directory/offline-unlink acceptance passes (2 tests), alongside
Core profile/receipt isolation. See the latest section of the current acceptance
for rollout evidence. Personal-link confirmation was subsequently supplied.

Customer account redesign: browser registration, a responsive header account menu and remembered sessions replace the earlier invitation/expiry-screen UX. See [ADR 0051](../../docs/adr/0051-customer-website-accounts.md) and the latest customer-account section of the [current acceptance](../../docs/status/2026-11-12-website-acceptance.md). Earlier audit checkpoints below remain dated evidence.

**Historical publication checkpoint, 2026-11-12:** commit `48d064a` deployed successfully through Vercel; corrected public metadata, DE/EN privacy and contact privacy links verified. KY-020 is completed. KY-021 is blocked: final www contact Origin is rejected while the old apex Origin reaches validation. Production `CONTACT_FORM_ORIGIN` must change and be redeployed. See [post-deployment evidence and owner inputs](../../docs/status/2026-11-12-website-acceptance.md#post-deployment-verification). The audit below preserves pre-publication findings.

Historical audit reviewed **2026-11-12**. The 2026-11-13 summary above is current; older review and
handover documents describe their respective dates, not present production health.
The current platform entry point is the
[website acceptance](../../docs/status/2026-11-13-website-acceptance.md); open
outcomes are KY-020–KY-024 in the [active backlog](../../docs/status/TODO.md#website-acceptance).

## Result

The website's functional source is integrated into `master`. The orange build
directories were generated verification output, not unmerged feature branches.
The informational website is publicly reachable. **A complete production
acceptance of contact mail, central account journeys and installable releases is
not established.** Passing a build or an HTTP check does not close those gates.

Audit baseline: local master `b6cdaf52a854e9064f4f3fd8043679e232a8e8d9`.
GitHub master returned `6dddda738d482521215a87887c0a099c6942365e`; the local
checkout was nine commits ahead, but `apps/website` had no committed differences
between those revisions. There were no additional local worktrees or unmerged
local branches. The audit's formatting, metadata, privacy-copy and documentation
changes are subsequent local changes, not a verified Vercel deployment.
Unrelated installer work appearing during the audit is preserved separately.

## Verified and corrected

| Area                 | Evidence and boundary                                                                                                                                                                                                                                                   |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Integrated source    | Website routes, components, locales, account/contact handlers, release catalog and tests are tracked on master and present in the checked GitHub baseline.                                                                                                              |
| Public pages         | Read-only HTTPS checks returned 200 for Home, Download, Hardware, Contact, Account, Privacy and English Home. Apex requests end on `https://www.kyrion.ch/`.                                                                                                            |
| Account availability | Public `GET /api/account/session` returned enabled=true with no session for an anonymous request. Provider discovery returned the expected HTTPS issuer. This is not proof of successful login, registration, mail or database persistence.                             |
| Local account flag   | The private local production file keeps accounts disabled. This does not describe the current Vercel environment, which reported enabled. No private values were displayed or changed.                                                                                  |
| Build and tests      | Production build, strict TypeScript, ESLint, Prettier and the complete isolated Playwright suite pass. See the final verification count below. Real SMTP and production account access are disabled in ordinary tests.                                                  |
| Canonical host       | Corrected source canonical/OG URLs, sitemap, robots and contact-origin template to the observed final `www` host. Tests now enforce the shared final origin. Public production still returned apex metadata during the audit and needs a deployment of this correction. |
| Privacy description  | Corrected DE/EN text that had incorrectly claimed there were no cookies. It now describes website account/flow HttpOnly cookies, central-provider cookies and separate website session storage. This factual correction is not a legal sign-off.                        |
| Documentation        | Removed stale claims that Privacy/Download do not exist or that the public account endpoint is definitely disabled. Download/Hardware pages exist; the installer catalog is still empty.                                                                                |
| Formatting           | Corrected five pre-existing formatting failures in route/configuration, installation presentation and installation/release tests.                                                                                                                                       |

## Build cleanup completed

Removed these seven unused, Git-ignored directories from `apps/website`:

```text
.next-account-checks
.next-account-production-readiness
.next-identity-full-website
.next-maintenance-build
.next-master-identity-website
.next-neon-account-readiness
.next-neon-checks
```

They contained 2,022 ordinary files totaling **182,128,160 bytes (173.7 MiB)**,
plus five generated dependency junctions. All absolute cleanup targets were
verified under this website directory and checked against running Node processes.
Dependency junctions were removed without traversing their targets before the
remaining generated trees were deleted. The referenced `pg` package and private
production configuration passed before/after preservation checks.

The current `.next` build remains. `node_modules`, private configuration,
tracked `identity-live`/`full-identity` tests, source, public assets and evidence
outside these seven generated folders remain. Orange generated/dependency
folders may still appear in IntelliJ; they are not integration failures.
Normal verification uses the current `.next`; explicitly running isolated
identity checks may regenerate their named build output. Historical evidence
links describe those dated runs and are not required runtime paths.

## Still open, with concrete completion evidence

| Priority                 | Item                                           | What closes it                                                                                                                                                                                                                                                                                                                            |
| ------------------------ | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1                       | KY-020: Deploy the audited corrections         | Review and deploy this source to the Vercel project; verify canonical, OG, robots, sitemap and DE/EN privacy text on the deployed final host. Current production's exact deployment commit was not accessible in this audit.                                                                                                              |
| P1                       | KY-021: Production contact mail                | Inspect the seven server-only Vercel contact variables without exposing values; confirm `CONTACT_FORM_ORIGIN=https://www.kyrion.ch`. Submit an explicitly authorized owner test and confirm inbox/spam, Reply-To and error handling. No real mail was sent by this audit. Source does not read the Pi's SMTP password file automatically. |
| P1                       | KY-022: Real central account journey           | With an authorized test account, verify registration availability, verification/reset mail, login callback, persisted session, logout and expiry in production. The public enabled flag and provider discovery alone are insufficient. Do not infer these journeys from the locally disabled test suite.                                  |
| P1 before wider exposure | KY-024: Abuse controls and operational privacy | Confirm deployed request limits for `POST /api/contact` in Vercel or another distributed boundary. Source exposes an abuse-check extension point but no shared limiter; platform rules were not accessible. Review privacy content, provider handling, retention/deletion and mailbox ownership against actual operations.                |
| Release gate             | KY-023: Actual installer downloads             | `src/content/releases.json` contains no releases. Publish and validate the intended signed/native artifacts, then populate the catalog from that publication. Download/Hardware pages are implemented; an empty catalog intentionally offers no installer links. This does not establish that no release exists anywhere else.            |
| Planned scope            | Dedicated docs portal/search/history           | The Docs page links to real repository guides. A separate documentation portal, search and historical article browser remain planned, not missing integration from the removed build folders.                                                                                                                                             |

No authenticated Vercel connector or CLI was available. Environment values,
deployment logs and firewall rules therefore remain unverified; no production
settings, DNS, database, identity account or public deployment was changed.

## Documentation and privacy follow-up

The root README, status index, single active TODO and continuation context now
share the same current acceptance report and KY-020–KY-024 gates. Account and
identity instructions distinguish the old loopback staging from current public
enabled/discovery observations; historical evidence is kept dated. The current
privacy pages explicitly distinguish session validity from stored-record and
backup retention, and each contact form links to its localized privacy page.
The existing browser regression now follows those links and checks rendered
cookie/retention copy in both languages. No retention duration or completed legal
review is invented. No further obsolete `.next-*` folders were found on recheck.

## Final verification

The final audit uses the repository's existing commands:

```sh
pnpm --filter website lint
pnpm --filter website format:check
pnpm --filter website typecheck
pnpm --filter website build
pnpm --filter website test
```

Final results after the corrective changes: **ESLint passed, Prettier passed,
TypeScript passed, production build passed, all 46 Playwright tests passed**
(complete documentation/privacy follow-up suite: 19.0 seconds). The initial unchanged baseline had 44
passing tests and five formatting failures. The two added regressions cover the
contact template's final origin and bilingual account-cookie disclosure; existing
metadata, sitemap and robots checks now enforce the final public host.

The documentation/privacy follow-up also verifies rendered DE/EN cookie and
retention content, follows each contact form's localized privacy link, and checks
relative documentation links plus unique active backlog IDs. The current public
recheck still sees the old privacy copy and canonical host, so publication and
real production acceptance remain open.
