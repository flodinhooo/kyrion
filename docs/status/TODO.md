# Kyrion Development TODO

Last updated: 2026-08-02

This file contains the immediate continuation point for the next development
session. The current implementation status is documented in [README.md](README.md).

## Next session: Refine the chat experience

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
- [ ] Replace prototype browser speech recognition and system TTS with
  explicitly selected local providers.
- [ ] Add interruption, local wake-word detection and voice-device settings.
- [x] Add `/activity` to the primary navigation with an honest Core-bound empty
  state.
- [ ] Define the Core-owned activity event contract and append-only log.
- [ ] Connect `/activity` to persisted Core events without exposing sensitive
  payloads.
- [ ] Define the Core/database boundary for conversation persistence.
- [ ] Add a local PostgreSQL development database after the first Core contracts
  are stable.
- [ ] Add PostgreSQL-backed conversation history and context compaction.
