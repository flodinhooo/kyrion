# Website sign-in method management, 2026-11-24

This follow-up extends the published enrollment slice with a website inventory
and removal of the user's own TOTP, passkey, security-key and recovery credentials.
It does not modify the owner's credentials or local installation permissions.

## Boundaries and behavior

- The website uses an ephemeral user access token against Keycloak's own-account
  read API. Existing user scopes and `delete_credential` action availability were
  checked; no administrator credential or new user role is added to the website.
- Only method ID/type/label/creation time and removal eligibility reach the UI.
  Provider payloads, seeds, private keys and tokens are not returned. Unknown or
  malformed metadata fails closed; an outage is distinct from an empty inventory.
- Refresh rotation and logout serialize under the existing session row lock.
  A failed inventory read commits the already rotated refresh token for retry.
  Account changes unmount and abort the old inventory so late data cannot reappear.
- Removal requires Origin, CSRF, explicit confirmation and a fresh own-account
  inventory/ownership check before an ID-bound one-use OIDC flow is created.
  The provider requests fresh authentication and its own final confirmation.
  Signed subject and recent `auth_time` are checked at return. Cancel is supported.
- Password removal is not offered. Without a password fallback, primary passkeys
  are conservatively protected, including when more than one exists; concurrent
  website requests must not remove the last primary login. Second-factor security
  keys are not mistaken for primary passwordless credentials.
- Existing signed-in sessions are not revoked globally by credential removal.
  A deleted credential may remain in a password manager. No cross-origin Signal
  API call or conversion of a provider database ID into a WebAuthn ID is attempted.

## Migration and audit

Apply website-only `migrations/005-credential-removal.sql` before deployment.
It adds the pending credential reference, an optional audit credential reference
and narrowly defined removal event codes. Existing sessions and flows survive.
The provider currently has event persistence disabled; its logging listener is
not treated as durable removal evidence. The website therefore appends correlated
request/return observations to its existing security log. An absent method is
recorded as observed absence, not inferred from an untrusted callback query flag.
Cancellation retaining the method and an unavailable post-action read have distinct
outcomes. No credential material is logged. Retention/deletion operations remain
under KY-024; expiry of a flow is not an audit retention deadline.

## Verification

Targeted real provider tests passed for inventory, explicit confirmation,
foreign-ID rejection, fresh-factor verification, cancel and targeted passkey removal.
All three combined real-service tests passed, including explicit TOTP/recovery
removal and the retained password login. Existing registration, recovery,
directory/link and local offline access regressions also passed against the
reviewed V49 runtime; unrelated Core/installer work is outside that proof.
Real PostgreSQL tests passed for migration idempotence, runtime grants, one-use
flow consumption, correlated audit observations and refresh survival after failed
reads. UI tests passed in DE/EN including names/dates, protected methods, required
confirmation, narrow widths, unavailable-versus-empty states and stale-account data.
The complete website suite passed 64 tests, with its opt-in database case run
separately. Lint, TypeScript and production build passed. Light desktop and dark
mobile inspection confirmed usable layout and no horizontal overflow.

## Published verification

Implementation `799c057` and the additional passwordless guard test `1447213`
were pushed to `master`. [Vercel deployment](https://vercel.com/florianrogenmosers-projects/kyrion-website/BskyXVw4zevQNqFPfxLq4NsGsUmd)
completed successfully for `1447213` at `https://www.kyrion.ch`.
The additional isolated real-provider test passed: after removing only the
synthetic account's password, passkey login still works and both the UI and a
direct removal request protect its primary passkey. The test restores its password.

A disposable public account passed all 16 browser/API stages: enrollment cancel,
TOTP/recovery/passkey enrollment and login, wrong TOTP rejection, own-method
inventory, missing-confirmation and foreign-ID rejection, removal cancellation,
targeted passkey/TOTP/recovery removal, remaining password login, and anonymous
read/action denial. The website audit contains four correlated removal starts,
one retained-method observation and three observed absences. The provider test
identity and its unlinked website account/sessions were removed; its generated
password was discarded. No personal account or method was changed.

Migration 005 has been applied to the verified dedicated website database before
publication. No Core/provider schema or personal credential was changed.

See [ADR 0095](../adr/0095-website-credential-management.md). Physical Windows Hello,
phone and security-key acceptance remains separate from virtual-authenticator proof.
