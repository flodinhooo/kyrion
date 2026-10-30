# ADR 0027: Explicit multi-provider model profiles

Status: Accepted for K-AI Milestone 01 implementation, 2026-10-30.

Keep the existing AI service and HTTP/NDJSON boundary. Introduce configured model
profiles and adapters for Ollama, OpenAI Responses, Anthropic Messages and Gemini
GenerateContent. Use the existing httpx dependency; do not add an orchestration
framework. Ollama remains the local default. Cloud profiles require server-side
enablement, credentials and explicit per-request consent. There is no automatic
fallback. Profile capabilities are explicit; unknown capabilities are unsupported.

Core controls external conversation context: cloud turns expose only the current
user message, never stored history, compacted summaries or confirmed memories.
Audit consent without prompt content. Web obtains that restricted context after
session/CSRF validation and makes cloud processing visible. AI independently
rejects cloud requests containing personal memory or conversation history.

Normalize text, complete tool proposals/results, usage, model identity, terminal
states and sanitized errors. Providers cannot execute actions. Existing Core
action policy, permissions, confirmations, idempotency and audit remain the sole
execution path. Web chat does not expose arbitrary tools or auto-execute proposals.
Native tool continuation is an internal typed capability, not a new authority.

Configure profiles as protected server-side JSON with environment-held API keys.
Do not discover paid models through network calls or benchmark cloud providers
automatically. Model identifiers are operator supplied, not a fixed release list.
Voice selects a local profile through the same configuration; avoid concurrent
changes to STT/TTS/Voice runtime files. Multimodal capabilities are represented as
metadata but unsupported content is rejected until a dedicated contract exists.

Use bounded connection/read/total deadlines, propagate cancellation and close
upstream streams. Record optional usage for future cost controls; no cost limit
or paid live-provider acceptance is implied. Cloud adapters are tested with
explicitly simulated transports before any separately authorized live API calls.
