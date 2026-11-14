# Optional central website accounts

The website's `/account` and `/en/account` pages implement an optional OIDC
relying party. They do not call installation Core, import local users, or grant
Space roles. Keycloak is the central authentication authority. The narrow
website BFF stores website-only opaque sessions in a dedicated central database;
it does not implement account passwords, identity brokering or an OAuth server.
Central account management and verified email remain in Keycloak.

## Customer account flow

[ADR 0051](../../docs/adr/0051-customer-website-accounts.md) supersedes the
invitation-only entry and short website sessions. Customers use Create account
or Sign in directly in the browser. Registration uses OIDC `prompt=create` with
one-use state, nonce and PKCE, not a website admin API or password grant.
Keycloak collects email/password, confirms the mailbox and handles recovery.
Names are optional; the email address is the username. Verified email is checked
in the signed identity proof before a website session is issued.

The header has a shared account control on desktop and mobile. Signed-in users
get account overview, website account settings and logout. The account page
shows customer actions and a separate Link account tab with code entry. No technical expiry
countdown or invitation request is shown. The shared session state rechecks on
focus, visibility and once per minute while visible, with stale-request guards
so an old request cannot resurrect the UI after logout.

Local connection still requires local password login, Profile / Link account, local password confirmation,
website code entry and provider approval. The local UI completes the approved
LINK automatically through Core; LOGIN keeps its existing confirmation. Website login
never guesses a local address, sends local credentials or joins accounts by email.
See [identity guide](../../docs/unified-identity.md) and the
[current lifecycle acceptance](../../docs/status/2026-11-14-identity-lifecycle.md).

## Configuration

Copy `account.env.example` values to protected deployment configuration.
For the later productive gate, `account.production.env.example` supplies the
HTTPS issuer/callback origin and a separate verified-TLS database placeholder,
with accounts still disabled. It is not a deployment or permission to initialize
a database. Confirm provider, region, credentials, schema/backup ownership and
the exact `https://www.kyrion.ch/api/account/callback` before enabling anything.
The public apex currently redirects308 to `www`; use the final canonical origin
for cookies, POST Origin checks and the registered callback, not the redirecting
apex. Do not register wildcard callbacks or both origins to hide this mismatch.
Accounts default to disabled. Disabled accounts do not discover a provider or
connect to PostgreSQL; the existing public site remains usable. When enabled,
all fields are required. URLs require HTTPS; explicit development HTTP is
restricted to loopback addresses and rejected in production mode. The callback
is always exactly `KYRION_WEBSITE_ORIGIN/api/account/callback`. No return URL is
accepted from the browser. Register only that exact callback in Keycloak, disable
implicit/direct grants, and require PKCE S256 and RS256 for this confidential
client. Never distribute this client's secret with local installations.

Apply `account-schema.sql` to a new central website PostgreSQL database using a
separate database account. Never use a local installation database or the
provider's own database. The script is additive/idempotent for this initial
schema. Subsequent deployed schema changes require versioned migrations.
Create an independent `kyrion_website_app` login with a random private password,
without administrative privileges or provider-administrator membership. Apply
`account-runtime-grants.sql` as the database owner only on this dedicated database.
It grants the runtime only the operations used by AccountStore, prevents schema
creation and audit deletion, and can be reapplied. The website does not use the
owner/migration credential. The existing `pg` driver enables SCRAM channel binding
when the server offers it, in addition to verified TLS.
On Vercel configure a managed PostgreSQL endpoint suitable for the runtime,
TLS and restricted credentials. The dedicated Neon provisioning described below
is separate from confirming the current Vercel runtime's deployed configuration.
No hosting or DNS changes are performed by these instructions.

Enabled account configuration rejects malformed PostgreSQL URLs without including
credentials in error messages. Production and every remote database require
`sslmode=verify-full`; modes such as `require`, `prefer` and `no-verify` are not
accepted as substitutes for explicit certificate/hostname verification. Only an
explicit loopback development configuration can omit this mode. Keep the
managed provider's hostname and CA validation; never set `rejectUnauthorized`
to false to make a connection work.

The owner-provisioned Neon database in Frankfurt was initialized separately from
the Pi provider and local installation databases. Private production values are
in ignored `apps/website/.env.production.local`; the website runtime credential
differs from the provisioning credential. Only the `KYRION_WEBSITE_*` fields
are needed by the account feature. `DATABASE_URL` is the same restricted runtime
URL for tooling compatibility, not the provider-owner URL. Local files do not
update Vercel settings automatically: import the private variables into the
website project's Production environment only. The initial provisioning retained
accounts disabled; the public endpoint now reports enabled, while full acceptance
is still open. Do not infer today's Vercel flag from the local file or copy
production credentials into Preview or local
installation configuration. Passwords and connection strings are never documentation.

For local start use [the isolated identity environment](../../infrastructure/identity/README.md).
Run the website development server with configured variables. Normal production
build/tests keep accounts disabled and make no external identity request.

## Contracts and security

- `POST /api/account/login` and `POST /api/account/register`: same-origin form, only a DE/EN locale is accepted.
  Uses Authorization Code with PKCE S256, random state/nonce, normal provider SSO. Registration adds `prompt=create`.
- `GET /api/account/callback`: consumes a five-minute browser-bound flow exactly
  once with atomic PostgreSQL `DELETE RETURNING`, then uses `openid-client` to
  check state, nonce, issuer, audience, expiry and RS256 signature through JWKS.
  Signature validation is explicitly enabled through `enableNonRepudiationChecks`.
- `GET /api/account/session`: returns website account UUID, expiry and CSRF value,
  never provider/session tokens. Responses use `Cache-Control: no-store`.
- `POST /api/account/logout`: requires exact configured Origin and session-bound
  CSRF header. Removes this website session, attempts provider renewal-credential
  revocation and clears its cookie. Logout does not require a successful refresh.
- `GET /api/account/manage`: returns to localized website settings; no arbitrary
  return URL or administration endpoint is accepted.
- `POST /api/account/profile` and `/api/account/password`: verified-session and
  CSRF-protected provider actions, returning to the website through a one-use,
  expected-subject-bound OIDC flow.

Account records contain only generated UUID, exact issuer and subject, uniquely
constrained together. No email, name, password, role or local user is copied.
Pairwise subjects across clients are deliberately not equated. Identity/access tokens are discarded after validation. Renewal credentials are
encrypted server-side and are never used as local Core API tokens.
The database stores only SHA-256 digests of random 256-bit session/flow cookie
credentials. Pending state/nonce/PKCE material is server-side and short lived.
Protect that database and backups as authentication material.
Session creation and revocation record account UUID, event code, timestamp and
correlation UUID transactionally in `website_account_event`, without tokens or
profile data. Restrict application credentials and operator access accordingly.

Cookies are host-only HttpOnly, Secure outside explicit development. The flow
cookie uses SameSite=Lax for the top-level provider callback; the session uses
SameSite=Strict. The UI keeps CSRF state in memory only. No authentication tokens
enter localStorage or URLs. The callback carries the protocol authorization code;
configure reverse proxies/hosting to omit its query string from access logs and
retain the no-referrer header. Authentication errors expose stable generic codes,
never provider exception details or tokens.

New website sessions have a persistent cookie and an absolute 30-day deadline.
A short-lived proof is renewed on demand at expiry (at most five minutes cached),
checking signature, issuer, audience, verified email and unchanged subject.
Renewal/logout serialize through a PostgreSQL row lock. Revoked proof deletes
the website session; transient provider failure denies access but retains the
credential for retry. Logout deletes locally before best-effort provider
revocation. Existing pre-migration sessions retain their original short expiry.
No offline grant or unbounded sliding deadline is used.

Refresh credentials use AES-256-GCM, a domain-separated HKDF key from the existing
high-entropy website client secret and the session digest as AAD. Only the
server holds the key; ciphertext is never returned through session JSON.
Rotating the client secret requires remembered users to sign in again. Apply
`migrations/002-remembered-sessions.sql` to the dedicated website DB before this
code is deployed; it adds nullable renewal columns and narrowly scoped UPDATE
rights. Fresh databases use the updated base schema and grants. Reapplying the
migration is safe. Local/Core schemas and session lifetimes are unchanged.

The configured provider needs online SSO and website-client idle/max sessions
bounded to 30 days; access/identity tokens remain short lived. Central blocking
is observed on the next renewal, not as instant global logout. Local linking,
local disablement and local password access remain independent.

Cookie validity is not data retention: expiry alone does not delete account,
security records or backups. Confirm operational deletion under KY-024.

## Website-initiated settings

The settings menu returns to the localized website account page. Profile and
password buttons start supported provider application-initiated actions and
return through the existing authorization-code callback. They require a verified
website session, exact Origin and constant-time CSRF verification. A one-use flow
also binds the expected central subject; a different signed identity is rejected.
Cancellation does not claim a successful update. Passwords remain exclusively at
the identity origin, which uses an inherited Kyrion login theme. No password grant,
iframe or provider administrator credential is introduced.

Apply `migrations/004-account-actions.sql` to the dedicated website database before
deploying these actions. It adds a nullable flow column; existing flows and
remembered sessions remain valid. Do not apply it to Core or Keycloak databases.
This slice covers profile and password editing, not MFA/passkey management.
See [ADR 0068](../../docs/adr/0068-customer-identity-experience.md).

## Verification details

`tests/account-security.spec.ts` exercises actual openid-client code against a
synthetic loopback OIDC server with real RSA signatures, including wrong signature,
issuer, audience, state, nonce, expiry and algorithm, configuration validation,
PKCE parameters and bilingual disabled UI. This is a simulated provider, not
Keycloak acceptance. The opt-in `identity-live.config.ts` suite separately tests
the real local Keycloak authorization-code flow, database sessions, replay,
logout and the public-client device grant. It creates/deletes a disposable
provider user and never calls production infrastructure. See the infrastructure
README for execution and actual results in the unified identity handover.

Dependencies: `openid-client` supplies maintained OAuth/OIDC validation instead
of handwritten protocol code; `pg` supplies transactional server-side session
persistence that works across website processes.

`tests/account-store.spec.ts` also checks encrypted credential tampering and
binding. With `KYRION_ACCOUNT_TEST_DATABASE` pointing strictly to the disposable
loopback database on 15559/website_acceptance, it exercises real PostgreSQL,
column-level least privilege, concurrent renewal/logout, revoked or changed
identities, temporary outages and absolute expiry. Ordinary CI skips only that
explicit database test; no production credentials are accepted by it.

## Visible code linking

[ADR 0052](../../docs/adr/0052-visible-code-account-linking.md) records the
streamlined consent/UI flow. The header exposes Link account, opening
`/account#connect` (or `/en/account#connect`). The code form POSTs to
`/api/account/connect`; it requires the website session, exact configured Origin
and session-bound CSRF. It normalizes the eight-character code and redirects
only to the configured issuer's `/device` page with `user_code` and locale.
No user-controlled host, local address or callback is accepted. The provider
checks the code; the local Core alone creates the link after signed proof.
The website does not claim success from submission or access local databases.
No webhook, inbound installation port or new general token relay is introduced.
