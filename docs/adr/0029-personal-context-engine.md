# ADR 0029: Personal, privacy-aware context assembly

Status: Accepted, 2026-10-30.

Extend personal_memory and owner_memory_settings; preserve existing confirmation,
CRUD and extractive conversation summaries. One Core ContextBuilder handles text
and Voice. Context is private to authenticated account IDs, never workspace-owner
substitution. No Space implementation exists in this checkout; the independent
Spaces worktree is not integrated or edited. Shared/business/document sources
remain denied until their authoritative access contracts exist.

Cloud receives only the current consented message. Additional disclosure
categories are represented as denied source policies, not a client-controlled
export switch. Local history retrieval and routing preferences require separate
opt-in. Memories remain opt-in, confirmed, active, unexpired and category-filtered.
Source descriptors contain identifiers/reasons/token estimates, not source text.
Unknown identities receive no personal context. Use bounded deterministic lexical
retrieval and existing persistence, no embeddings or new database dependencies.
