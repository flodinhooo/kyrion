# Optional central website accounts

The website's `/account` and `/en/account` pages implement an optional OIDC
relying party. They do not call installation Core, import local users, or grant
Space roles. Keycloak is the central authentication authority. The narrow
website BFF stores website-only opaque sessions in a dedicated central database;
it does not implement account passwords, identity brokering or an OAuth server.
Central account management and verified email remain in Keycloak.

## Invited users and local connection

The account page explains the separate local and central credentials in DE/EN.
During the private test phase, a user requests an invitation through Contact;
there is no public self-registration endpoint. Operators create a regular
central user without assigning a password or marking their email verified,
then use Keycloak's `execute-actions-email` with `VERIFY_EMAIL` and
`UPDATE_PASSWORD` and a 30-minute lifespan. The user proves mailbox access and
sets their password themselves. Never publish action URLs or credentials.
Do not send the invitation to the website OIDC callback: the invitation has no
matching browser-bound state/PKCE flow. After setup, start website login afresh.

The page shows three local linking steps both before and after website sign-in:
local password login, Profile / Kyrion account / Connect, then provider code
approval and explicit local confirmation. The signed-in view omits the invitation
request. No local URL is guessed, local credentials are never sent to this site,
and matching email addresses do not create a link. If the option is missing or
disabled, the local installation needs the current UI/Core and an operator's
central-login opt-in. See [identity guide](../../docs/unified-identity.md).

## Current acceptance (2026-11-12)

The public anonymous session endpoint reports enabled=true and HTTPS provider
discovery succeeds. The private local production file and example templates
still default to disabled; that is not evidence that Vercel is disabled. The
dedicated Neon setup has dated evidence, but current Vercel database settings
and successful public user journeys were not authenticated or exercised in this
audit. See [current acceptance](../../docs/status/2026-11-12-website-acceptance.md)
and KY-022, within the wider KY-003 identity gate. No registration, reset mail or
login/logout acceptance follows from the enabled flag alone.

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
These validity bounds are not data-retention promises: the current store removes
expired flow rows when beginning a new flow, excludes expired sessions from reads
and deletes a session on logout, while account/security records and backups have
separate lifecycles. Confirm retention/deletion procedures under KY-024; do not
describe token expiry as deletion of all stored records.
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
