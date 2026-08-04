# ADR 0004: Explicit, Owner-Controlled Personal Memory

- Status: Accepted
- Date: 2026-08-04

## Context

Conversation history is not permission to retain personal facts indefinitely.
Kyrion needs a separate memory layer that remains useful across conversations
without turning model inference into hidden profile storage. Sensitive beliefs,
health, relationships and political information require especially clear
consent and control.

## Decision

Personal memory is disabled by default and configured per owner. Memory records
are stored separately from conversations, context summaries and executable
capabilities. The first extraction path accepts only an explicit "remember
this" request and creates a proposal; it never creates confirmed memory
directly.

Every record has an owner, category, concise content, sensitivity, origin,
status, optional source conversation and message, and creation, update and
confirmation timestamps. The first categories are `preference`, `person`,
`project`, `value` and `other`. Sensitivity is explicitly `standard` or
`sensitive`. Both standard and sensitive proposals require confirmation in the
first slice; sensitive proposals are visually identified.

Core owns opt-in, validation, persistence, confirmation, correction and
deletion. The browser uses authenticated, CSRF-protected same-origin routes.
The AI service receives no database access and does not automatically extract
memories. Confirmed memories are not yet injected into prompts; relevant
retrieval and visible influence require a separate evaluated slice.

Forgetting physically deletes the selected memory in this local prototype.
Data-minimised activity events record setting changes, proposal, confirmation,
correction and deletion without recording memory content.

## Consequences

- Chat history and long-term memory have independent lifecycles.
- Users can inspect, correct and forget every retained item.
- No memory is retained merely because a model inferred it.
- Disabling memory prevents new proposals but does not silently delete existing
  records; the profile continues to expose them for review or deletion.
- Relevant retrieval, conflict/supersession handling and retention expiry are
  deliberate follow-up work.
