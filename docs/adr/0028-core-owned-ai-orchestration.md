# ADR 0028: Core-owned AI routing, preferences and usage reservations

Status: Accepted for K-AI Milestone 02, 2026-10-30.

Core owns per-account preferences, workspace administrator policy, deterministic
model selection, consent, request reservations and usage settlement. AI continues
to own provider translation and local speech. Web cannot report authoritative
usage or select around policy: generation streams through Core, which observes
AI metadata directly and reloads authoritative conversation context.

Add tables only. Use existing conversations permissions for personal settings/
generation and system_settings permissions for workspace policy. Administrator
restrictions take precedence. Default preferences are local-only; cloud context
remains current-message-only, never stored memory/history. Server cloud enablement
and explicit provider-specific consent remain necessary. No history export option
is introduced by this milestone.

Reserve conservative token/cost estimates transactionally under an account lock
before each provider attempt. Prices must come from explicit profile metadata;
unknown price/currency blocks a monetary-limited request. Usage comes from Core's
upstream stream, never browser input. Pending/uncertain attempts retain their
reservation rather than silently refunding potentially incurred usage. Estimates
and actual/provider-reported counters remain distinguishable. No distributed
exact billing or automatic reconciliation is claimed.

Fallback requires both administrator and user opt-in and explicit profile lists.
It is restricted to the same disclosure boundary (local-to-local or the same
consented cloud provider), before visible text/tool events, and only explicit
availability/rate-limit errors. Timeout, truncated stream, unknown outcome,
tool activity, disconnect and partial output never trigger fallback. Each attempt
has its own usage/audit record; a request ID cannot execute twice.

Text and Voice use this same Core router. Voice stays local until it has a
dedicated cloud-consent UI. Do not alter wake detection, STT, TTS or audio formats.
Continue using HTTP/JSON/NDJSON and the existing provider adapters, without new
services, queues or SDK dependencies.
