# Local Authentication and Conversation Ownership

## Implemented boundary

Kyrion Core is the authentication authority. Fresh first-owner setup requires a
locally provisioned setup secret; existing installations retain their identities
and never need another setup secret. See [ADR 0023](adr/0023-security-bootstrap-and-delegation.md)
and the [security hardening report](status/2026-10-11-security-hardening.md).

The `/signup` and `/login` first-owner flow accepts a one-time setup secret in a
password input. Web forwards it only in `X-Kyrion-Setup-Secret`, removes it from
the credentials body and never returns it. Core reads a protected file configured
by `KYRION_BOOTSTRAP_SECRET_FILE`; the file contains exactly a 32-byte CSPRNG
base64url value (43 characters), valid for 30 minutes from its modification time.
Missing, malformed, expired, future-dated, symlinked or POSIX group/world-accessible
files fail closed. No secret is generated, printed or exposed by Core. Failed
attempts use the existing bounded backoff limiter. Operators must provision the
file privately, owner-only (0600 on POSIX), and protect its parent directory and
Windows ACLs. Installer v1 will implement provisioning and private delivery; this
is not implemented host onboarding. An expired unclaimed file requires explicit
local renewal, never a remote reset endpoint.

Flyway V31 adds a permanent initialization marker, initialized to closed if users
already exist. Owner creation, marker consumption, initial roles, session and
successful audit are one transaction; the existing global PostgreSQL advisory
lock admits one concurrent winner. Failure rolls everything back and leaves the
claim retryable until expiry. Once consumed, the file cannot reopen setup, even
if accounts are subsequently absent. Restore must preserve this marker and the
original credential/audit keys. Existing startup must not refresh bootstrap files.

Additional accounts require a cryptographically random invitation, defaulting to
one use and 24 hours. [Kyrion Spaces](kyrion-spaces.md) adds bounded uses, role
selection, listing, revocation and local fragment URLs. Only users explicitly granted `invitations:create` can issue
one. Actor and workspace are separate, including for delegated administrators.
Invitation redemption, account/session creation and audit are transactional.
Registration assigns the selected non-OWNER role, or the Space default role,
without changing existing grants. Inviter delegation is checked at creation and
redemption. The new account belongs to exactly that Space.
Repeated initial seeding only grants defaults to newly created roles.

Core checks effective permissions and workspace ownership. Non-owner delegates
cannot assign OWNER, manage owner identities, modify their own roles, or grant
permissions beyond their effective permissions. Managing a target or existing role
also requires covering its current permissions. Consequently default ADMIN cannot
manage a default USER/VIEWER role containing personal rights outside ADMIN's grant
set; the owner must choose an explicitly bounded delegation. The primary owner
cannot be disabled or stripped of OWNER. Role keys remain immutable on update;
display names and grants can change. Workspace advisory locks serialize mutations
and recheck active identity/permissions, with the audit in the same transaction.
Session authentication inside these transactions avoids taking last-seen row locks
before the workspace lock.

Local calendar events are shared workspace resources: this data model has no
personal-local-calendar flag. Access requires `calendar:read/create/update/delete`;
existing non-owner grants remain unchanged, and new permissions are not silently
granted to them. Owners can explicitly delegate shared-calendar access. Google
connections and calendars are scoped to the authenticated account, including
OAuth completion and catalogue visibility. Their metadata is excluded from the
shared device list. Local calendar mutation/audit is atomic. Google writes record
intent and outcome with one correlation ID outside long database transactions;
a provider success followed by local audit failure leaves an intent requiring
operator reconciliation. Appointment text and secrets are never audit summaries.
`syncToGoogle` is an optional Boolean (missing/null means false); strings, numbers
and containers are rejected. Without a target calendar it stores intent only.
Explicit per-event mapping enables the bounded [calendar synchronization](calendar-synchronization.md)
flow, with acting-account isolation, provider preconditions and pending deletion.

Personal sessions, conversations, memories, exports and retention stay scoped to
the individual account. No existing sealed audit rows are rewritten or data moved.
No production deployment or hardware acceptance is implied by automated checks.

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
- `POST /v1/auth/register` (requires a valid invitation code)

Authenticated Core endpoints:

- `GET /v1/auth/me`
- `POST /v1/auth/invitations` (original owner only)
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
chat sidebar reads the current owner's recent conversations, and
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

Registration coverage includes duplicate names, expiry, concurrent single-use
redemption, anonymous and invitee enrollment denial, shared room writes and
device commands with a mocked Nanoleaf adapter, real actor attribution and
continued personal conversation/session isolation. No test commands real hardware.

## Web navigation

The authenticated root (`/`) opens the existing home and room controls; `/home`
remains available for existing links. Chat starts at `/chat`, and saved
transcripts retain `/conversations/{id}`. Recent conversations and the new-chat
action appear only on these chat routes. Conversation history, model discovery
and AI health polling are not requested by ordinary workspace pages; model
settings load their catalog when opened. The shared header names the current
page instead of presenting an AI identity or preview badge globally.
