# Website TOTP, passkeys and recovery, 2026-11-24

The owner requested optional, simple security enrollment from the website and
authorized publication of the complete committed master, including parallel
installer commits. Uncommitted installer work is excluded.

## Implemented

Website account settings provide Authenticator app, Add passkey and Save recovery
codes actions in German and English. The existing signed-in session, exact Origin,
constant-time CSRF check, state, nonce, PKCE and signed expected-subject binding
protect all five supported account actions. The allowlist rejects inherited
properties and arbitrary provider/admin action names. No database migration or
new runtime dependency is needed. No local Core authorization rule is changed.

Keycloak owns TOTP secrets, recovery codes, WebAuthn challenges and credentials.
Passwordless credentials require discoverability and user verification. Their RP
ID belongs to the identity origin, not the marketing website. The website keeps
its opaque server session; provider credentials are not exposed through it.
Password fallback remains available and enrollment is optional. A user explicitly
confirms saving recovery codes in the inherited provider form.

Credential enumeration/removal and a verified lost-device support process remain
separate work; no unverified request clears an existing second factor. Actual
Windows Hello, phone and physical security-key acceptance remains distinct from
virtual authenticator evidence. Nothing enrolls the owner's personal account.

## Verification

- Website lint, TypeScript and production build passed.
- 58 ordinary website tests passed; the unrelated opt-in PostgreSQL case skipped.
  Two initial resource-related browser timeouts passed on the final run without
  concurrent integration-test compilation. No product timeout was relaxed.
- Real isolated Keycloak enrollment, invalid TOTP rejection, fresh TOTP login,
  recovery-code login and CTAP2 resident passkey registration/login passed.
  Authenticator assertion events prove passkey use after clearing cookies.
- The provider rejects an enrollment OTP replay within its original time window;
  the test waits for a genuinely fresh code, without fake clocks or SQL expiry.
- The integration fixture restores provider policy and deletes its synthetic user.
  Secrets and failure artifacts remain ignored and must not be published.

All three combined real-service identity tests also passed, including the
existing signup, recovery, directory, local link/login/expiry and offline unlink
journeys. The reviewed V49 Core runtime was used; unrelated Core work is separate.
The existing public provider policy and browser execution were privately backed
up and the reviewed optional passkey/recovery settings activated without restart,
image upgrade, credential reset or mandatory enrollment.

Public deployment verification is recorded below when completed.
See [provider configuration](../../infrastructure/identity/SECURITY.md)
and [ADR](../adr/0070-website-security-enrollment.md).
