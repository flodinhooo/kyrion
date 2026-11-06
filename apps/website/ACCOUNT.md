# Optional central website accounts

The website's `/account` and `/en/account` pages implement an optional OIDC
relying party. They do not call installation Core, import local users, or grant
Space roles. Keycloak is the central authentication authority. The narrow
website BFF stores website-only opaque sessions in a dedicated central database;
it does not implement account passwords, identity brokering or an OAuth server.
Central account management and verified email remain in Keycloak.

## Configuration

Copy `account.env.example` values to protected deployment configuration.
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
On Vercel configure a managed PostgreSQL endpoint suitable for the runtime,
TLS and restricted credentials; the existing informational deployment does not
already provide that infrastructure. No hosting or DNS changes are included.

For local start use [the isolated identity environment](../../infrastructure/identity/README.md).
Run the website development server with configured variables. Normal production
build/tests keep accounts disabled and make no external identity request.

## Contracts and security

- `POST /api/account/login`: same-origin form, only a DE/EN locale is accepted.
  Uses Authorization Code with PKCE S256, random state/nonce, forced fresh login.
- `GET /api/account/callback`: consumes a five-minute browser-bound flow exactly
  once with atomic PostgreSQL `DELETE RETURNING`, then uses `openid-client` to
  check state, nonce, issuer, audience, expiry and RS256 signature through JWKS.
  Signature validation is explicitly enabled through `enableNonRepudiationChecks`.
- `GET /api/account/session`: returns website account UUID, expiry and CSRF value,
  never provider/session tokens. Responses use `Cache-Control: no-store`.
- `POST /api/account/logout`: requires exact configured Origin and session-bound
  CSRF header. Revokes this website session, then clears its cookie.

Account records contain only generated UUID, exact issuer and subject, uniquely
constrained together. No email, name, password, role or local user is copied.
Pairwise subjects across clients are deliberately not equated. All provider
tokens are discarded after validation, and are never used as general API tokens.
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

Sessions last at most 15 minutes and never beyond the ID token's expiry (the
development realm currently gives five-minute tokens). There is no refresh-token
storage or silent indefinite renewal. Central suspension becomes effective at
the next login; an already issued website session may remain valid for its
bounded remaining duration. Website logout, central account suspension, local
access suspension and removing a local account link are separate operations.
Provider-wide logout/backchannel revocation is a future improvement; no claim
of immediate global logout is made. Operators may revoke central website
sessions directly by account UUID in `website_session` if incident response
requires immediate website revocation.

## Verification

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
