# ADR 0003: Core-Owned Conversation Context and Deterministic Compaction

- Status: Accepted
- Date: 2026-08-04

## Context

The first persisted conversation slice stored owner-scoped transcripts in Core,
but the browser still supplied the complete transcript to the AI service and
later replaced the stored conversation. A modified browser could therefore
change historical model context even though it could not read another owner's
conversation. Long conversations also had no explicit context budget.

## Decision

Core is the authority for conversation order and model context. The browser
sends a conversation identifier and exactly one new user message. Next.js
authenticates the request and forwards that message to Core. Core appends it for
the authenticated owner and returns the ordered, token-bounded context that
Next.js may send to the AI service. The streamed assistant response is appended
through Core before Next.js forwards the completion event to the browser.

The initial runtime context budget is 3,072 estimated tokens for the currently
configured 4,096-token Ollama runtime, leaving room for Kyrion's system prompt
and generated output. Token estimation is deterministic and intentionally
conservative rather than provider-specific.

If the stored transcript exceeds the budget, the newest messages consume at
most three quarters of the context budget and remain verbatim. Older messages
are compacted into a bounded, deterministic extractive summary. Core persists
the summary with its inclusive source-position range and algorithm version.
The same range and version reuse the same summary; a future algorithm change
must use a new version and may regenerate it from the authoritative messages.
The Web interface is told whenever compaction influenced a response.

Model-generated summaries are intentionally deferred. This keeps essential
context assembly available without AI, avoids introducing a second model call,
and removes malformed summary output as an input boundary in this first slice.

## Consequences

- Browser-supplied historical messages no longer influence the chat path.
- Owner checks, ordering, persistence and context selection remain in Core.
- Context selection is reproducible and inspectable.
- The original conversation messages remain stored; compaction does not delete
  or overwrite them.
- Interrupted generations currently leave the persisted user message without a
  persisted partial assistant message. Recovery semantics remain follow-up work.
- Provider-aware tokenizers and semantic, model-generated summaries may be
  introduced later behind a new summary algorithm version.
