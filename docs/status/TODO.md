# Kyrion Development TODO

Last updated: 2026-08-04

This file contains the immediate continuation point for the next development
session. The current implementation status is documented in [README.md](README.md).

## Completed: Local authentication and ownership

- [x] Add an identity and session database schema without creating a default
  user or exposing public registration.
- [x] Hash passwords with Argon2id using unique salts.
- [x] Generate opaque 256-bit session tokens and persist only SHA-256 hashes.
- [x] Implement and test session creation, expiry, last-seen updates and
  revocation in Core.
- [x] Add a one-time local-owner setup endpoint and setup screen.
- [x] Add Core login, current-user and logout endpoints.
- [x] Set the session through a same-origin `HttpOnly` and `SameSite` cookie;
  use `Secure` whenever Kyrion is served over HTTPS.
- [x] Add CSRF protection to authenticated state-changing requests.
- [x] Protect private Core and Next.js routes through authoritative session checks.
- [x] Add automated integration coverage that proves owner isolation with two
  users before multi-user setup is introduced.
- [x] Record authentication success, failure and logout as data-minimised
  security activity events without logging credentials or raw tokens.
- [x] Add automated tests for cookie flags, CSRF validation, invalid
  credentials, expiry, revocation, session rotation and PostgreSQL owner
  isolation.
- [x] Add authenticated password change with current-password verification,
  revocation of all existing sessions and a fresh session cookie.

## Completed chat and voice refinement

- [x] Render assistant responses as Markdown instead of displaying Markdown
  syntax such as `**bold**` as plain text.
- [x] Add polished styling for headings, paragraphs, lists, links, inline code
  and fenced code blocks in both themes.
- [x] Improve spacing and readable line lengths for longer responses.
- [x] Add persistent standard, comfortable and large typography options that
  scale body text, headings and page titles without enlarging layout chrome.
- [x] Keep the conversation scrolled to the newest content while a response is
  streaming, without overriding intentional user scrolling.
- [x] Add a Kyrion/Velora system prompt so the assistant identifies itself as
  Velora and describes its role accurately instead of repeating the base
  model's identity.
- [x] Define sensible defaults for response language, tone and length.
- [x] Refine the loading, stop-generation and error states.
- [x] Manually exercise the primary chat, history and authentication flows in
  both light and dark mode.
- [ ] Complete a systematic German and English visual pass for every settings
  and error state.

## Verification

- [x] Run `pnpm lint`.
- [x] Run `pnpm build`.
- [x] Start the full local stack using
  [Local Development Startup](../development-startup.md).
- [x] Send short, long and list-based prompts through
  `http://localhost:3000`.
- [ ] Add a dedicated code-block prompt to the next visual regression pass.
- [x] Confirm that streaming and continued persisted conversations work after
  adding Markdown rendering.

## After the chat refinement

- [x] Add an AI-service readiness state to the web status indicator.
- [x] Add a controlled per-device model selector backed by the deployment
  allowlist.
- [x] Add a dedicated model page with metadata from the local model runtime.
- [x] Add a controlled per-device benchmark with a transparent model
  recommendation.
- [x] Introduce conversation identifiers.
- [x] Add an initial browser-backed Voice Mode opened from the Velora orb.
- [x] Add per-language browser voice selection, previews and speaking-rate
  controls.
- [x] Stream visible answer tokens immediately for reasoning-capable models
  without waiting for an invisible Qwen thinking pass.
- [x] Begin speaking completed sentences while later answer text is still being
  generated.
- [x] Isolate voice turns so old messages and cancelled utterance callbacks do
  not enter the next response queue.
- [x] Add a centred, wider Voice Mode transcript with subtle spoken-word focus.
- [ ] Replace prototype browser speech recognition and system TTS with
  explicitly selected local providers.
- [ ] Add interruption, local wake-word detection and voice-device settings.
- [x] Add `/activity` to the primary navigation with an honest Core-bound empty
  state.
- [x] Define the Core-owned activity event contract and append-only log.
- [x] Connect `/activity` to persisted Core events without exposing sensitive
  payloads.
- [x] Define the Core/database boundary for conversation persistence.
- [x] Add a local PostgreSQL development database after the first Core contracts
  are stable.
- [ ] Add authenticated actor ownership, retention policy and tamper-evidence to
  the activity log before treating it as a compliance audit trail.
- [x] Add active conversation highlighting, editable titles, confirmed
  deletion, history states and visible persistence errors.
- [x] Add owner-scoped PostgreSQL conversation and message persistence after the
  authentication slice is complete.

## Next session: Authoritative context and compaction

- [x] Document the typed contract for Core-owned conversation context supplied
  to the AI service.
- [x] Load stored messages by authenticated owner and conversation ID instead of
  treating a browser-supplied full transcript as authoritative.
- [x] Define a transparent context token budget for the selected models under
  the current shared 4,096-token runtime configuration.
- [x] Preserve the latest turns verbatim while compacting only older context.
- [x] Persist summaries with source ranges, versioning and regeneration rules.
- [x] Tell the user when older context was compacted.
- [x] Add tests for ordering, owner isolation and deterministic context
  selection. Malformed model-summary output is not applicable because the first
  compaction algorithm is deterministic and does not invoke a model.
- [x] Persist a visibly stopped partial assistant response through the new
  authoritative turn contract.

## Then: Explicit personal memory

- [x] Record an ADR for personal-memory consent, sensitivity and ownership.
- [x] Add a profile-level opt-in with German and English explanations.
- [x] Support an explicit “remember this” request as the first extraction path.
- [x] Require confirmation before retaining sensitive memories such as religion,
  health, relationships or political beliefs.
- [x] Add a profile view to inspect, correct and forget individual memories.
- [x] Retrieve only a small relevant set and make memory influence visible.
- [x] Keep memory records separate from conversation history and executable
  plugin authority.

## Security and operations follow-up

- [ ] Add login throttling and temporary backoff before remote exposure.
- [ ] Add active-session listing and selective session revocation to the profile.
- [ ] Define conversation and activity retention policies.
- [ ] Define personal-memory retention expiry and archival policy.
- [ ] Add activity actor scoping and tamper evidence before making compliance
  claims.
- [ ] Add backup and restore verification for PostgreSQL data.

## Later product slices

- [ ] Return to the first controlled integration and capability contract after
  context and personal-memory foundations are stable.
- [ ] Replace browser speech providers only after explicitly selecting suitable
  local STT and TTS runtimes.
