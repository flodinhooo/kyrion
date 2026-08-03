# Kyrion Development TODO

Last updated: 2026-08-02

This file contains the immediate continuation point for the next development
session. The current implementation status is documented in [README.md](README.md).

## Next session: Complete local authentication

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
- [ ] Add automated integration coverage that proves owner isolation with two users
  before multi-user setup is introduced.
- [ ] Record authentication success, failure and logout as data-minimised
  security activity events without logging credentials or raw tokens.
- [ ] Add integration tests for cookie flags, invalid credentials, expiry,
  revocation and session rotation.

## Completed chat and voice refinement

- [x] Render assistant responses as Markdown instead of displaying Markdown
  syntax such as `**bold**` as plain text.
- [x] Add polished styling for headings, paragraphs, lists, links, inline code
  and fenced code blocks in both themes.
- [x] Improve spacing and readable line lengths for longer responses.
- [x] Keep the conversation scrolled to the newest content while a response is
  streaming, without overriding intentional user scrolling.
- [x] Add a Kyrion/Velora system prompt so the assistant identifies itself as
  Velora and describes its role accurately instead of repeating the base
  model's identity.
- [x] Define sensible defaults for response language, tone and length.
- [x] Refine the loading, stop-generation and error states.
- [ ] Verify all changes in German and English as well as light and dark mode.

## Verification

- [x] Run `pnpm lint`.
- [x] Run `pnpm build`.
- [x] Start the full local stack using
  [Local Development Startup](../development-startup.md).
- [ ] Send short, long, list-based and code-based prompts through
  `http://localhost:3000`.
- [ ] Confirm that streaming and cancellation still work after adding Markdown
  rendering.

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
- [ ] Define the Core/database boundary for conversation persistence.
- [x] Add a local PostgreSQL development database after the first Core contracts
  are stable.
- [ ] Add authenticated actor ownership, retention policy and tamper-evidence to
  the activity log before treating it as a compliance audit trail.
- [ ] Add context compaction, conversation deletion and retention controls.
- [x] Add owner-scoped PostgreSQL conversation and message persistence after the
  authentication slice is complete.
