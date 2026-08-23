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
For a deliberately trusted local development LAN only,
`KYRION_INSECURE_LAN_HTTP=true` permits a production Web build to issue the
same non-`Secure` host-only cookie used by the development server. This must
remain disabled for internet-facing or otherwise untrusted networks.

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
- `GET /v1/auth/sessions`
- `DELETE /v1/auth/sessions/{sessionId}`
- `GET /v1/activity`
- `GET /v1/devices`
- `POST /v1/devices/observations/refresh`
- `POST /v1/device-commands`
- `GET /v1/conversations`
- `GET /v1/conversations/{id}`
- `PUT /v1/conversations/{id}`
- `PATCH /v1/conversations/{id}`
- `DELETE /v1/conversations/{id}`
- `POST /v1/conversations/{id}/turns`
- `POST /v1/conversations/{id}/turns/complete`
- `GET /v1/memory`
- `PUT /v1/memory/settings`
- `POST /v1/memory/proposals`
- `POST /v1/memory/{id}/confirm`
- `PATCH /v1/memory/{id}`
- `DELETE /v1/memory/{id}`

The browser uses same-origin Next.js routes under `/api/auth` and
`/api/conversations`; it does not receive the Core session token in JSON.

## Conversation persistence

Flyway V3 adds `conversation` and `conversation_message`. Every conversation
has a required `owner_id`; all reads and updates combine the requested ID with
the authenticated owner ID. Messages have stable UUIDs, an explicit order and
validated `user` or `assistant` roles.

The browser submits exactly one new user message. Core appends it, creates an
explicit `started` turn and supplies the owner-scoped, token-bounded context.
Next.js persists server-observed assistant output before forwarding completion.
Completed, visibly stopped and failed turns are recorded distinctly. The
sidebar reads the current owner's recent conversations, and
`/conversations/{id}` restores a saved transcript.

Flyway V6 adds opt-in personal memory as a separate owner-scoped store. Explicit
German or English remember requests create proposals only after opt-in. Every
proposal requires confirmation and remains inspectable, correctable and
deletable through the profile.

## Current limitations

- Login throttling applies a temporary exponential backoff after five failed
  attempts and returns `LOGIN_RATE_LIMITED` with `Retry-After`.
- The profile lists owner-scoped active sessions and can selectively revoke
  another session. There is no password-recovery flow.
- Password change is implemented and rotates the current credential by
  revoking every existing owner session before returning a fresh session.
- Conversation titles are derived from the first user sentence, shortened to a
  readable length and capitalised. Owners can rename or delete conversations;
  both operations enforce owner isolation and deletion requires confirmation in
  the Web UI.
- Legacy transcript replacement remains available for the existing management
  contract but is no longer used by chat generation.
- Confirmed-memory retrieval, memory conflicts/supersession and retention
  policies remain follow-up work.

Activity events now carry ownership independently from actor identity. The
authenticated activity feed returns owner events plus safe installation-level
system events. This boundary is the prerequisite for future retention without
cross-owner exposure or deletion.

## Automated verification

Core integration tests run against a disposable PostgreSQL 17 Testcontainer;
they never use the development database or owner account. They cover one-time
setup closure, successful and rejected login, protected HTTP resources,
logout/revocation, password rotation across multiple sessions, password hash
persistence and owner-isolated conversation reads, updates, renames and deletes.
Turn lifecycle, context compaction and the memory
opt-in/proposal/confirmation/update/deletion flow are covered as well.

The Web test suite covers strict CSRF token comparison, explicit German and
English memory-request recognition and the security policy for session and
CSRF cookies. Run the suites with `gradlew.bat test` in
`services/core` and `pnpm test` in `apps/web`.
