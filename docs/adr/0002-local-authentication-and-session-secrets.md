# ADR 0002: Local Authentication and Session Secrets

- Status: Accepted
- Date: 2026-08-02

## Context

Persisted conversations and future integrations require explicit ownership.
Kyrion currently runs as a local single-installation system, but storing data
without an authenticated owner would force insecure contracts or a later broad
migration. The user has explicitly chosen not to require full-disk encryption
for the current installation.

## Decision

Kyrion Core remains the authentication and authorisation authority. The first
authentication flow will create one local owner through an explicit one-time
setup; it will not expose unrestricted public registration.

Passwords are stored only as salted Argon2id hashes. Core creates opaque
256-bit random session tokens. The raw token is returned only for delivery in a
protected browser cookie, while PostgreSQL stores only its SHA-256 hash. This
hash is appropriate because session tokens are high-entropy random secrets;
passwords continue to use the deliberately expensive Argon2id algorithm.

Web authentication will use a same-origin, server-managed session cookie with
`HttpOnly` and `SameSite` attributes, `Secure` under HTTPS, session rotation at
authentication boundaries and CSRF protection for state-changing requests.
Authentication credentials and session tokens must not be stored in browser
local storage. A later native mobile client may use a separate token transport
stored in the operating system's protected credential storage.

Conversation content will not be hashed because Core and the user must be able
to read it. Application-level conversation encryption is not part of the first
local slice. Database access remains localhost-bound, credentials remain
outside version control and backups must be handled transparently.

## Consequences

- Conversation records can be owner-scoped from their first migration.
- A database leak does not directly reveal passwords or usable session tokens.
- A stolen active raw session token remains sensitive until expiry or
  revocation, so cookie flags, HTTPS for remote access and short session policy
  remain important.
- Password recovery cannot recover the original password; it must replace the
  hash through an explicitly authorised recovery flow.
- Full-disk and application-level content encryption remain optional future
  protections rather than claims of the current implementation.
- Setup, login, current-user, logout, cookie and CSRF endpoints remain required
  before the prepared session model is exposed to the Web application.
