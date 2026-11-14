# Website acceptance: published state, 2026-11-13

This is the current website acceptance. The [2026-11-12 report](2026-11-12-website-acceptance.md)
preserves earlier audit, migration and rollout evidence. This update does not
certify unrelated installer changes, physical integrations or the whole platform.

## Publication and verified behavior

- Published master commit: `eb07775975a70b0f2f5f437dba3220fde9e0febb`.
  It includes frontend fix `b899f1e` and the Modern Web Guidance integration.
- [Vercel production deployment](https://vercel.com/florianrogenmosers-projects/kyrion-website/8hJVzTdqaVUcUFWQc7jarbMJSAFa)
  reports success; this status was rechecked for this documentation update.
- DE/EN home/contact pages, account, localized connect pages and privacy returned
  HTTP 200 in the post-deployment smoke check.
- A real browser verified live contact-field correction in German and English:
  invalid email stays invalid; a valid correction removes the field error and
  `aria-invalid` without another submission. The tested mobile viewport had no
  horizontal overflow; no browser runtime errors occurred.
- Contact POST with an empty object from the canonical origin returned
  `400 CONTACT_INVALID`; a foreign origin returned `403 CONTACT_REJECTED`.
  These are non-delivering boundary checks, not successful-mail delivery tests.
- Anonymous installation listing and reporting returned 401. Account/session
  responses use no-store. No real link or contact email was created by the smoke.
- Local Core health and the existing local Web login route remained HTTP 200.
  Publishing source does not itself update installed local/Pi Core artifacts.

The owner supplied browser evidence on 2026-11-12: provider device approval,
local linked status and the installation appearing in the website account.
The personal login/link/directory journey is therefore confirmed for that user;
the earlier pending-code instruction is superseded. No personal address or
account identifier is reproduced in this documentation.

## Software verification and bounded changes

The recorded frontend checks passed 282 local-Web tests and 56 Website tests;
the separate opt-in Website database test was intentionally skipped in that run.
Both applications passed types, lint and production builds; relevant formatting
checks passed. Earlier isolated database/provider acceptance retains its dated
scope and is not replaced by the skipped opt-in test.

The first three [MWG proposals](2026-11-13-modern-web-guidance-audit.md#implementation-follow-up-mwg-01-through-mwg-03)
are implemented and included in the publication:

1. Device write failure/timeout releases pending controls and announces failure;
   writes are never automatically repeated. Network, HTTP, invalid JSON/schema,
   deadline and subsequent explicit-attempt cases have synthetic unit coverage.
2. Directory reads are single-flight with completion-based scheduling, cleanup
   abort and bounded backoff. Browser coverage includes slow/focus races, hidden
   tabs, timeout recovery and session-change isolation.
3. Corrected text-field errors clear against the existing validation rules.
   Browser coverage includes DE/EN, untouched fields, revalidation on submit and
   server-provided field errors without another send.

The account menu and Radix primitives are retained. No new runtime dependency,
automatic device action or real mailbox delivery was introduced by these fixes.
The public browser smoke verifies the field correction directly; device failure
and authenticated directory race behavior were tested with synthetic responses,
not by interrupting production devices or another user's account session.

## Remaining website acceptance

The [Nov14 identity lifecycle follow-up](2026-11-14-identity-lifecycle.md) closes
the bounded public KY-022 journey below. Its actual renewal evidence covers
330 seconds across the proof-cache boundary, not 30 elapsed days.

| Backlog | Remaining outcome                                                                                                | Input or work needed                                                                                                                                                                                    |
| ------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| KY-021  | Receiving inbox/spam and Reply-To acceptance                                                                     | Owner confirms a real contact message arrived and replying targets its sender. Successful submission/Origin correction is already evidenced.                                                            |
| KY-022  | New public customer registration, mailbox verification, password recovery, remembered-session renewal and logout | A controlled new-user journey and real reset/renewal/logout checks; the owner's existing login/link is complete, not a substitute for every lifecycle case.                                             |
| KY-024  | Production abuse controls and privacy/data operations                                                            | Verify deployed request/rate limits and document responsibility, retention, deletion and recovery for Vercel, identity, database and mailbox. An extension point or cookie expiry is not this evidence. |
| KY-023  | Public reviewed installer downloads                                                                              | Complete release/signing/distribution and clean-host gates, then publish reviewed artifact metadata. The website catalog remains empty.                                                                 |
| MWG-04  | Optional native account-menu exploration                                                                         | Deferred by explicit owner preference; not a blocker and no rewrite is scheduled.                                                                                                                       |

KY-020 publication is complete. Contact Origin correction and the personal
account link are no longer blocked/open tasks. No additional website refactor is
required to close this publication task. Broader HOME family/provider, hardware,
voice, recovery and installer gates remain in [the active backlog](TODO.md).

## Evidence limits

This is a successful production deployment and bounded smoke, not a claim of
complete end-to-end mail acceptance, all account lifecycle cases, multi-browser
accessibility certification, load testing or a generally available installer.
No credentials, private logs or real user payloads are included in this report.
