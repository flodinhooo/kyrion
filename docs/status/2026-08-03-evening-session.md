# Evening Session Handoff — 2026-08-03

Approximate focused development time: two hours.

## Outcome

The session advanced Kyrion from prepared authentication primitives to a usable,
protected and owner-scoped local assistant workspace.

### Authentication and profile

- Added one-time local-owner setup without public registration.
- Added login, current-user, logout and password-change contracts in Core.
- Added the same-origin Next.js authentication boundary.
- Session credentials use `HttpOnly`, `SameSite=Strict` cookies and `Secure`
  under HTTPS.
- Authenticated mutations use double-submit CSRF protection.
- Password changes verify the current password, revoke every previous session
  and rotate the current browser to a fresh session.
- Added a protected profile route with password management and placeholders for
  future personal details and session management.
- Authentication success, denial, setup, logout and password changes produce
  data-minimised security activity events.

### Owner-scoped conversation history

- Added Flyway V3 with owner-scoped conversations and ordered messages.
- Persisted completed and visibly stopped chat turns in PostgreSQL.
- Restored conversations after reload and allowed them to continue normally.
- Replaced demo sidebar history with the owner's persisted conversations.
- Added active-conversation highlighting, inline rename and confirmed deletion.
- Added explicit loading, empty and unavailable history states.
- Added visible conversation-save failures without discarding the current UI
  transcript.
- Automatic titles use the first meaningful sentence, remain within a readable
  length and always begin with a capital letter.
- Manual titles are preserved when later messages are saved.

### Accessibility and presentation

- Added a profile entry in the top-right application bar.
- Added per-device standard, comfortable and large typography preferences.
- Typography scales body text, Markdown headings and display titles without
  enlarging icons or layout chrome.
- Comfortable is the new default; the selection is persisted in the browser.
- German and English resources were added for all new visible functionality.

### Automated verification

- Added disposable PostgreSQL 17 Testcontainers integration tests.
- Covered one-time setup, HTTP authentication contracts, rejected credentials,
  logout, password rotation and conversation owner isolation.
- Covered the conversation HTTP lifecycle: save, rename, delete and subsequent
  not-found response.
- Added Web policy tests for session-cookie flags and CSRF token matching.
- Added automatic-title tests including capitalisation and truncation.
- Full Core tests passed.
- Web tests passed: two files, six tests.
- `pnpm lint` passed.
- `pnpm build` passed.
- Flyway V1 through V3, Core health and AI-service health were verified.

The integration tests use a disposable database and do not modify the real
owner account, sessions or conversation history.

## Defects found and corrected

- Corrected PostgreSQL advisory-lock result handling that initially caused the
  owner setup endpoint to return HTTP 500.
- Corrected the authentication exception handler to be a global controller
  advice; the HTTP integration test exposed the incorrect registration.
- Ensured a manually renamed conversation is not overwritten by later automatic
  persistence.

## Architecture decisions preserved

- Core remains the authentication, ownership and persistence authority.
- The browser never receives the raw Core session token in JSON.
- Conversation reads, writes, renames and deletes always include the
  authenticated owner identifier.
- The AI service still proposes rather than executes privileged actions.
- Personal memory will be a separate, inspectable owner-scoped layer rather
  than hidden model fine-tuning. See [Personal Memory Direction](../personal-memory.md).

## Known limitations

- Chat context is still supplied from the mounted client conversation. Core
  does not yet assemble an authoritative token-bounded context.
- Long conversations have no compaction or summary pipeline.
- Personal memory is designed but not implemented.
- Login throttling is not implemented; the stack must remain local-only.
- Active-session listing and selective revocation are not exposed in the UI.
- Activity retention and tamper evidence remain future hardening work.
- Browser speech remains the transparent prototype voice provider.

## Recommended continuation

Start with server-owned conversation context and compaction. Once that boundary
is stable, implement the smallest explicitly confirmed personal-memory slice.
External device integrations should follow after these assistant foundations
unless product priority changes.
