# Kyrion Development TODO

Last updated: 2026-08-01

This file contains the immediate continuation point for the next development
session. The current implementation status is documented in [README.md](README.md).

## Next session: Refine the chat experience

- [x] Render assistant responses as Markdown instead of displaying Markdown
  syntax such as `**bold**` as plain text.
- [x] Add polished styling for headings, paragraphs, lists, links, inline code
  and fenced code blocks in both themes.
- [x] Improve spacing and readable line lengths for longer responses.
- [ ] Keep the conversation scrolled to the newest content while a response is
  streaming, without overriding intentional user scrolling.
- [ ] Add a Kyrion/Velora system prompt so the assistant identifies itself as
  Velora and describes its role accurately instead of repeating the base
  model's identity.
- [ ] Define sensible defaults for response language, tone and length.
- [ ] Refine the loading, stop-generation and error states.
- [ ] Verify all changes in German and English as well as light and dark mode.

## Verification

- [ ] Run `pnpm lint`.
- [ ] Run `pnpm build`.
- [ ] Start the full local stack using
  [Local Development Startup](../development-startup.md).
- [ ] Send short, long, list-based and code-based prompts through
  `http://localhost:3000`.
- [ ] Confirm that streaming and cancellation still work after adding Markdown
  rendering.

## After the chat refinement

- [ ] Add an AI-service readiness state to the web status indicator.
- [ ] Decide whether model selection remains deployment-controlled or becomes
  available in Settings.
- [ ] Introduce conversation identifiers.
- [ ] Define the Core/database boundary for conversation persistence.
- [ ] Add PostgreSQL-backed conversation history and context compaction.
