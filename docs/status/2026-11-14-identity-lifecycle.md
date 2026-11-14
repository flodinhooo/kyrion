# Public identity lifecycle and customer settings, 2026-11-14

This follow-up separates actual public lifecycle evidence from broader identity
operations and release gates. No personal account password was changed.

## Public lifecycle evidence

An owner-designated, previously absent test identity was created through public
website registration. Real verification and recovery messages arrived through
the configured mail service. Only new matching test messages were read.
Credentials, mail links and raw mail remain outside version control.

Passed against `https://www.kyrion.ch` and `https://auth.kyrion.ch`:

- Public registration and email confirmation, followed by website login.
- Forgot-password email and setting a different generated password.
- Reopening the consumed recovery link did not offer another password reset.
- Closing the browser context and restoring persistent cookies retained login.
- Waiting 330 real seconds crossed the five-minute proof cache. The website
  renewed proof without reauthentication; cookie value and absolute expiry stayed
  unchanged. This is short-proof renewal, not 30 elapsed days of evidence.
- Website logout remained effective after reload.

The configured absolute website lifetime remains 30 days. Provider revocation,
browser cookie deletion or expiry can require login sooner. Website logout and
local installation sessions remain independent.

## Customer settings slice

[ADR 0068](../adr/0068-customer-identity-experience.md) retains Keycloak as the
credential authority while removing its generic account console from the normal
website settings entry. Profile and password actions require a verified session,
Origin/CSRF checks and a signed-subject-bound one-use callback. An inherited
Kyrion CSS theme preserves upstream security forms and password-manager semantics.
The visible authentication origin remains `auth.kyrion.ch`; this is not a
same-origin password form or a new password service.

Local verification passed: website lint, TypeScript and production build;
57 ordinary website tests with the opt-in database case skipped; both separate
PostgreSQL tests including migration idempotence, runtime permissions, one-use
flow round-trip and subject lookup; and both real-service acceptance tests.
The real-service journey included profile/password changes, recovery replay,
anonymous/invalid-CSRF rejection, same-site settings navigation, local linking,
central login expiry, offline local access and unlinking without changed roles.
Light desktop/dark mobile theme inspection found no horizontal overflow and
confirmed preserved `autocomplete="current-password"`. The light brand contrast
was corrected after visual inspection. No provider upgrade is included.

## Deployment and public settings checks

Source `5591ffb2b6dd9fa8db76366a1e6dfb248832cab5` was pushed to `master` and
[Vercel reported success](https://vercel.com/florianrogenmosers-projects/kyrion-website/GbJA7w2LTr6cDr9vyG1KZnSPtNsR).
Migration 004 was applied only to the verified dedicated website database before
deployment. The existing provider retained its reviewed 26.8.2 image, database,
secrets and realm configuration. Its Compose/realm settings were privately
snapshotted before adding the read-only theme mount and selecting `kyrion`.
Existing realm import was skipped; production caching remains enabled.

Public browser checks passed for profile editing, action cancellation, password
change, returning to the website, the localized website settings target and fresh
login with the changed test password. Both anonymous action endpoints returned 403. The inherited Kyrion stylesheet was present on the actual public action page.
The newly created test identity and its website account/session rows were removed
after checking its exact identity, creation date and absence of linked installations.
The test password was discarded. No mailbox or personal account was deleted.

The isolated Core journey used the reviewed V49 packaged runtime, not unrelated
in-progress installer/Core work. This slice changes no local authorization rules.
MFA/passkey administration, cross-browser certification, 30-day elapsed testing,
abuse limits and operational backup/deletion/recovery remain separate work.
