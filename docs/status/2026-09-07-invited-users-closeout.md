# Invited users: session closeout

Date: 2026-09-07

## Result

Additional users can join the existing local installation with their own
credentials and control its shared devices. This implements the requested
friend-access slice; granular RBAC remains deferred.

1. The original owner opens Profile > Security > Invite a friend.
2. The owner explicitly creates and shares an invitation code.
3. The friend opens `/signup` on the same installation and supplies the code,
   a username, password and password confirmation.
4. Registration creates an individual account and session. The friend can
   control and manage the shared devices, rooms and integrations.

Codes expire after 24 hours and can be redeemed once. Only their SHA-256 hashes
are persisted. Invalid, expired and previously redeemed codes are rejected;
duplicate usernames do not consume an otherwise valid invitation. Only the
original resource owner can create invitations. All UI text is available in
German and English, including the explanation of granted access.

## Boundaries and implementation

Core remains the authentication and execution authority. First-owner setup
remains a one-time operation. `/v1/auth/invitations` requires an authenticated
original owner; `/v1/auth/register` requires an invitation. The Web invitation
route additionally enforces CSRF and does not cache invitation responses.
Registration retains the existing protected session-cookie transport.

Flyway V27 adds `user_account.workspace_owner_id` and
`registration_invitation`. Invitation redemption, account creation and session
issuance are transactional. The server derives the resource scope from the
invitation, independently of the authenticated actor. Existing resource rows
and sealed audit history are not moved or rewritten.

Shared access covers devices, rooms, integrations, gateways, satellite
enrollment, actions and the installation activity feed. Passwords, sessions,
conversations, personal memory, personal backups and retention settings remain
individual. Shared HTTP actions retain the actual user as audit actor; action
idempotency also distinguishes actors.

The decision is recorded in [ADR 0019](../adr/0019-shared-installation-registration.md).
See also [authentication](../authentication-and-conversations.md) and
[Web experience](../web-experience.md).

Main implementation areas are `apps/web/src/app/signup`, the authentication
forms and profile invitation panel, `apps/web/src/app/api/auth`, and Core's
`security` package, shared-resource controller boundaries and activity recording.

## Verification from the implementation session

- Web: full ESLint check, production build and TypeScript check passed.
- Web: 80 tests in 32 files passed, including invitation CSRF/session checks,
  propagation of Core's invitation denial and non-cacheable code delivery.
- Core: the full run executed 163 tests. One new integration test initially
  failed because its room request omitted `roomType`; the fixture was corrected
  to match the Web request, and the complete authentication persistence test
  class then passed. The other tests passed in the full run.
- Core: `bootJar` built successfully.
- PostgreSQL integration coverage includes concurrent single-use redemption,
  duplicate usernames, expiry, shared room creation, shared device control,
  real actor attribution and personal conversation/session isolation.
- Device control used a mocked Nanoleaf adapter, not physical hardware.
- `git diff --check` passed.

These are implementation-session results, not new deployment or physical
acceptance evidence. The documentation closeout does not rerun application tests.

## Handoff and remaining work

- Update and restart Core and Web together. Core applies V27 on startup. No
  rollout or restart was performed as part of this implementation session.
- Verify the complete invitation/signup flow in two browser sessions on the
  intended installation, including German/English labels and small screens.
- Verify one actual device command from the friend's account and inspect its
  actor in Activity. Physical acceptance remains outstanding.
- RBAC, account administration/revocation and invitation revocation remain
  follow-up work. Expiry and one-use redemption are implemented.
- Unrelated working-tree changes were preserved. This closeout does not commit,
  deploy or change running services.

The existing [platform consolidation](2026-09-06-platform-consolidation.md) and
Velora acceptance backlog remain valid; this bounded feature does not reopen
their deferred scopes.
