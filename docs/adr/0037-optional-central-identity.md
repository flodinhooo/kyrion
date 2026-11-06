# ADR 0037: Optional central identity with explicit local links

Status: accepted for implementation; no production infrastructure is implied.

## Context

At `fe5e65a`, Core implements Argon2id passwords, opaque hashed sessions,
one-time host-secret OWNER setup, invitations, local recovery, active Space
membership and a single-Space runtime guard. The website is public with no
accounts or identity database. No OIDC provider exists in source or configured
infrastructure. Uncommitted primary-checkout V42/V43 belong to Gateway/calendar
work and are excluded; this change reserves additive V44 and ADR 0037.

## Decision

Use self-hosted Keycloak, rather than implementing an authorization server.
Its maintained OIDC implementation supports public device clients, confidential
website clients, PKCE S256, explicit device confirmation and account management.
See the official [OIDC guide](https://www.keycloak.org/securing-apps/oidc-layers)
and [administration guide](https://www.keycloak.org/docs/latest/server_admin/).
`auth.kyrion.ch` is an example configuration only, requiring later DNS/TLS setup.

Keycloak owns central identities and verified email. A separate website BFF
uses openid-client for authorization code + PKCE S256, state and nonce, and a
central PostgreSQL database for short-lived opaque website sessions and flows.
This narrow website session boundary conveys no platform authorization. Core
continues to own every local authentication, identity link and permission.
Central identity storage and local installation databases never share tables,
credentials or access. The development provider has its own database as well.

Local installations are public clients without shared secrets. They use RFC 8628
device authorization because LAN installations cannot safely register arbitrary
callbacks and are not assumed internet-reachable. No callback/token relay is
introduced. The device flow has no redirect, state, nonce or PKCE parameters;
its secret device code remains server-side. The browser explicitly confirms the
displayed user code at the provider and subsequently confirms the local action.
Core uses Nimbus OIDC validation with a fixed RS256 algorithm, issuer, audience,
authorized party and expiration checks. ID tokens establish identity only; local
API calls always use opaque Core sessions. Access/refresh tokens are discarded.

Links use `(issuer, subject)` with database uniqueness, never email or username.
Pairwise subjects across website/local clients are separate identities; no
cross-client central account ID or automatic reconciliation is needed. Linking
requires a current local session and password, provider proof and explicit
confirmation. Local passwords and hashes are never copied. Removing a link
requires the local password, preserves that login method, and revokes sessions
created through central authentication. No flow changes roles or membership.

An unknown central identity must first obtain local access through the existing
protected setup or invitation and then explicitly link. Central login cannot
create a local user, membership or OWNER. This deliberately reuses enrollment
and Business email-proof policy rather than creating another enrollment path.

Local sessions continue independently of the provider. Central sessions expire
within 15 minutes and no later than their identity proof, then require a new
provider round trip; there is no sliding cloud-token offline lifetime. Blocking
a central account cannot invalidate an offline local session immediately. Local
disablement and membership revocation still apply on every local request.
Logout revokes one relying-party session, central blocking denies future central
proof, local blocking denies local access, and unlinking removes only the mapping.
No global logout or automatic password/local-account synchronization is implied.

## Consequences

All existing accounts remain usable without configuration/network access.
Only issuer and subject are imported locally, with Keycloak authoritative for
these values; no profile or email synchronization is implemented. Local username,
credentials, roles, memberships and all user content remain locally authoritative.
Provider operations fail closed without preventing local login. Live DNS/TLS,
provider deployment, registration policy and operational backup remain external
acceptance steps. Installer changes and multi-Space enablement are out of scope.
