# Local Authentication and Conversation Ownership

## Implemented boundary

Kyrion Core is the authentication authority. A fresh installation exposes a
one-time owner setup status and setup command. Once the first account exists,
setup is permanently closed and there is no public registration endpoint.

Core hashes passwords with Argon2id and stores only SHA-256 hashes of opaque
256-bit session tokens. The raw token crosses the trusted localhost boundary
once, from Core to the Next.js server. Next.js removes it from the response and
sets `kyrion_session` as an `HttpOnly`, `SameSite=Strict` cookie. The cookie is
marked `Secure` in production or when `KYRION_HTTPS=true`.

Next.js creates a separate random `kyrion_csrf` cookie. Authenticated mutating
requests must echo this value in the `X-Kyrion-CSRF` header. Comparison is
timing-safe. The CSRF token is not an authentication credential.

Private browser routes perform an authoritative Core session lookup during
server rendering. Private Next.js API routes repeat that check. Core separately
requires a bearer session on protected `/v1` resources, so bypassing the Web UI
does not bypass the authority boundary.

## Endpoints

Public Core endpoints:

- `GET /v1/auth/setup/status`
- `POST /v1/auth/setup`
- `POST /v1/auth/login`

Authenticated Core endpoints:

- `GET /v1/auth/me`
- `POST /v1/auth/logout`
- `POST /v1/auth/password`
- `GET /v1/activity`
- `GET /v1/conversations`
- `GET /v1/conversations/{id}`
- `PUT /v1/conversations/{id}`

The browser uses same-origin Next.js routes under `/api/auth` and
`/api/conversations`; it does not receive the Core session token in JSON.

## Conversation persistence

Flyway V3 adds `conversation` and `conversation_message`. Every conversation
has a required `owner_id`; all reads and updates combine the requested ID with
the authenticated owner ID. Messages have stable UUIDs, an explicit order and
validated `user` or `assistant` roles.

After a successful assistant stream, the Web application persists the complete
visible transcript. The sidebar reads the current owner's recent conversations,
and `/conversations/{id}` restores a saved transcript. Partial assistant output
is retained when a stopped stream already produced visible text.

## Current limitations

- Login throttling and temporary lockout are not implemented. Core remains
  localhost-only; this must be addressed before remote exposure.
- There is no password recovery or session-management screen.
- Password change is implemented and rotates the current credential by
  revoking every existing owner session before returning a fresh session.
- Conversation titles use the first user message and are not editable yet.
- Transcript replacement is intentionally simple for the current single-client
  slice; concurrent editing and optimistic versioning are not implemented.
- Context compaction, deletion and retention policies remain follow-up work.

## Automated verification

Core integration tests run against a disposable PostgreSQL 17 Testcontainer;
they never use the development database or owner account. They cover one-time
setup closure, successful and rejected login, protected HTTP resources,
logout/revocation, password rotation across multiple sessions, password hash
persistence and owner-isolated conversation reads and updates.

The Web test suite covers strict CSRF token comparison and the security policy
for session and CSRF cookies. Run the suites with `gradlew.bat test` in
`services/core` and `pnpm test` in `apps/web`.
