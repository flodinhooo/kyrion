# ADR 0051: Browser registration and remembered website sessions

Status: accepted for implementation, 2026-11-12 (owner requested).

## Decision

Replace the invitation-only website entry with browser self-registration owned
by Keycloak. Use the standard OIDC `prompt=create` with the same one-use state,
nonce and PKCE callback as sign-in. Keycloak collects credentials and verifies
email; the website never receives passwords or administrative credentials.
Enable self-registration and password recovery with email verification and
existing brute-force protection. No local membership or automatic link follows.

The shared header exposes sign-in/register when anonymous and an account menu
with account, management and logout when authenticated. The account screen shows
customer actions; local connection help is secondary and expandable.

Remember website sessions for at most 30 days, using an opaque persistent Secure
HttpOnly SameSite=Strict cookie. Keep identity tokens short lived. Refresh the
central proof on demand when it expires; serialize refresh/logout through a
database row lock. Invalid/revoked proof deletes the local website session;
temporary provider failure denies authenticated access but preserves retry.
The same issuer and subject must hold after refresh. There is no browser token
storage or offline grant, and no extension of the absolute 30-day deadline.

Refresh credentials are stored only in the dedicated website database, encrypted
using AES-256-GCM, a domain-separated HKDF key derived from the existing
high-entropy server-side website client secret, and the session digest as AAD.
They never enter the session JSON, logs, browser or Core. Rotating the client
secret invalidates remembered credentials and requires a fresh sign-in. A
separate managed encryption-key service can replace this when operationally
needed; no new provider or browser-visible secret is introduced now.

Apply an additive versioned website migration with nullable renewal columns so
existing sessions retain their original expiry. Grant UPDATE only on those
columns. Use normal online refresh credentials; bound Keycloak website/SSO idle
and maximum sessions to 30 days without increasing access-token lifetime.
Website logout removes its row first and attempts provider credential revocation.
Central revocation is observed no later than the current short identity-proof
expiry. Provider-wide sign-out and local session lifetimes remain separate.

This supersedes ADR 0041's short website-session/no-refresh restriction only for
the public website. Local Core authentication, device linking, offline sessions,
permissions and credentials are unchanged. Update privacy/account documentation
to distinguish remembered cookie validity from data-retention procedures.

## Verification and rollout

Test real OIDC registration parameters, signed refreshed identity, encryption
tamper/session binding, database serialization, revocation, transient failure,
logout, and DE/EN responsive header/account states. Apply migration only to the
dedicated central website DB; preserve private provider configuration snapshots.
Verify public registration navigation without creating unsolicited accounts or
sending test mail. Real mailbox/registration completion remains owner acceptance.

References: [Keycloak registration](https://www.keycloak.org/docs/26.5.7/server_admin/index.html#_oidc_clients),
[session controls](https://www.keycloak.org/docs/26.8.0/server_admin/).
