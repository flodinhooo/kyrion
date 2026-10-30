# K-AI Milestone 01: model providers

Implemented foundation, 2026-10-30. No production deployment, cloud credentials,
paid API requests or additional SDK/runtime dependencies were introduced.
See [ADR 0027](adr/0027-multi-provider-ai-foundation.md).

## Supported paths

| Provider      | API                                                | Status                                  |
|---------------|----------------------------------------------------|-----------------------------------------|
| Ollama        | `/api/chat` NDJSON, local catalog/show             | Default; real local generation verified |
| OpenAI        | Responses `/v1/responses`, SSE                     | Implemented; simulated transport tests  |
| Anthropic     | Messages `/v1/messages`, SSE                       | Implemented; simulated transport tests  |
| Google Gemini | `v1beta/models/{id}:streamGenerateContent?alt=sse` | Implemented; simulated transport tests  |

Model IDs come from protected operator configuration, not a baked-in cloud model
list. Gemini accepts both `gemini-...` and `models/gemini-...` official identifiers.
Actual account/model availability requires a separately approved live acceptance
test. No model compatibility is inferred from a vendor name or arbitrary alias.

All adapters translate system instructions, messages, text streaming, complete
tool proposals/results, usage where available and sanitized errors. The existing
message start/delta/completed/error events and local model IDs remain supported.
New events are `model.selected`, `usage`, `tool.call`, `tool.result`; clients must
ignore metadata they do not use. A tool result is supplied as a typed input
message; providers never execute it or perform device/account actions.

## Server configuration

Copy `services/ai/model-profiles.example.json` into protected local configuration,
for example `E:/Kyrion/Data/config/model-profiles.json`. Do not edit actual private
configuration as part of a source review or copy secrets into the JSON example.
The JSON file contains model metadata, not API keys. The AI process reads:

```dotenv
KYRION_MODEL_PROFILES_FILE=E:/Kyrion/Data/config/model-profiles.json
KYRION_AI_CLOUD_ENABLED=false
OPENAI_API_KEY=replace-with-server-side-key
ANTHROPIC_API_KEY=replace-with-server-side-key
GEMINI_API_KEY=replace-with-server-side-key
```

The optional profile file is absent by default: the existing Ollama settings (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
`KYRION_ALLOWED_MODELS`) continue to work.
The AI service reads its process environment; an example `.env` is documentation,
not an automatic dotenv loader. Pass variables through the existing trusted
launcher/service environment. Core reads `KYRION_AI_CLOUD_ENABLED` through its
existing Spring environment configuration as well; both Core and AI must approve
cloud processing. No key is needed by Web or Core. No setting enables fallback.

Replace placeholder model IDs with identifiers supported by your account. Set
the corresponding profile's `enabled` field to true only after reviewing model
capabilities and potential costs, supply its key, and explicitly enable the
server flag. The example leaves every cloud profile disabled. Credentials stay
in server-side protected environment configuration; they never appear in the
model catalog, browser, query parameters or normalized errors. Key fields are
excluded from Settings representations. Keep Ollama's endpoint on a trusted
local/self-hosted runtime; the label is not a network-attestation mechanism.

Profiles contain a stable selection `id`, `provider`, provider `modelId`, `label`,
explicit `capabilities`, optional `contextLength`, `enabled`, `maxOutputTokens`
and connection/read/total `timeouts`. Optional input/output cost-per-million and
currency fields prepare later budget controls. These are informational metadata,
not an enforced spending limit. Provider locality is derived, never caller-set.
Unknown capabilities remain unsupported. Basic legacy Ollama chat/streaming is
retained, while known tool/vision/audio flags can come from local model metadata.
Explicit profiles are authoritative. Multimodal flags are preparatory metadata;
this milestone accepts text/tool content, not images, recordings or arbitrary
attachments in the chat contract.

Default and voice profiles must be enabled and local. A cloud profile can only be
selected explicitly for a chat request. Neither a failed local model nor a model
selection preference silently changes processing to the cloud. Disabled or
missing providers remain visible in the authenticated Web model settings. Local
catalog failure does not hide configured cloud profiles. Cloud model discovery
and benchmarking never trigger remote API calls; benchmarks remain local-only.

## Disclosure and Core policy

Web resolves the selected profile from the server catalog. For cloud requests it
shows the provider/model and a notice about data and possible charges, and asks
for confirmation on every submitted message. The same-origin route retains
session and CSRF checks. The browser cannot submit tool definitions, arbitrary
history, personal memories, API endpoints or provider credentials through chat.

Core receives `externalProvider` and `externalConsent: "current_message"` when
starting a cloud turn. It checks server enablement, records a correlated consent
event and returns only the current user message. It does not invoke the personal
memory selector or return history/compaction summaries. The local conversation
and turn remain persisted. Consent auditing and turn creation share a transaction.
Missing/invalid consent is denied before turn persistence. The existing optional
token budget now correctly defaults when omitted/null in the JSON boundary.

Web independently refuses any cloud context containing history/memory, including
an older Core response. AI independently requires its server flag, configured
key, enabled profile and `cloudConsent: true`, and rejects cloud requests with
memory or anything other than one current user message. User-supplied system
messages cannot replace Kyrion's instructions. A user may intentionally include
sensitive information in the current message; the notice is not content redaction.

Cloud *conversation-history export* and automatic tool continuation are not
enabled. Adapter-level tool-result serialization is implemented and tested,
including Gemini call IDs/thought signatures and OpenAI reasoning-state replay,
but HTTP cloud continuation carrying prior turns is deliberately refused. A
future Core-owned bounded tool-turn/disclosure contract must authorize that path
before exposure. No generic autonomous cloud/device agent is claimed.

## Tool safety and execution boundary

`ToolDefinition`, `ToolCall`, `ToolResult` and `TokenUsage` are bounded Pydantic
models. Tool arguments must match a listed name and a validated JSON Schema
subset: explicit object properties/required keys, closed objects, nested arrays,
strings, numeric/Boolean/null types, enums and basic size/range constraints.
Unsupported schema keywords (including external references) fail closed. The
subset is deliberate; arbitrary JSON Schema is not advertised as supported.
Unknown tools, malformed arguments, duplicate calls/results and unmatched results
are rejected. Partial JSON argument deltas never become executable intent.
Normalized tool events are proposals; consumers must wait for successful terminal
completion and then use Core validation, permissions, confirmations, idempotency
and audit before executing anything. A provider response is never authorization.

Web chat supplies no native tools and does not execute returned proposals. The
existing deterministic device interpreter and Core Action Orchestrator still
handle bounded supported device requests, irrespective of the chosen chat model.
Their existing action tests remain in the Core suite. There is no new device
control endpoint, execution bypass or unrestricted tool loop in this milestone.

## Voice and runtime ownership

AI resolves `interactionMode: "voice"` through `voiceProfileId`, defaulting to the
same local profile as text. This overrides the legacy Core caller's fixed model
selection without editing its parallel-owned `VoiceDialogueController.kt`.
The literal `gemma3:1b` remains in that caller pending coordinated cleanup, but it
does not select the model in the migrated AI service. New profiles are shared
configuration; the browser preference does not reconfigure a Satellite. Cloud
voice is intentionally unavailable. Parakeet, Chatterbox, capture, VAD, audio
playback, Pi credentials and runtime startup behavior were not changed here.

## Streaming and errors

Cloud SSE and local NDJSON are normalized to Kyrion NDJSON. The HTTP contexts
close on cancellation/early exit. Connection/read/total deadlines are bounded and
configurable; no automatic retries or model fallback cause hidden requests.
Missing terminal events and malformed streams fail visibly; output limits and
refusals are not reported as complete answers. Usage is request-stream metadata,
not a durable billing ledger or an exact monetary charge calculation.

Errors include `PROVIDER_NOT_CONFIGURED`, `CLOUD_NOT_ALLOWED`, `MODEL_DISABLED`,
`CAPABILITY_UNSUPPORTED`, `PROVIDER_AUTH_FAILED`, `RATE_LIMITED`, `REQUEST_TIMEOUT`,
`CONTEXT_NOT_ALLOWED`, `CONTEXT_LIMIT_EXCEEDED`, `TOOL_CALL_INVALID`,
`PROVIDER_REFUSED`, `OUTPUT_LIMIT_REACHED`, plus existing model/stream errors.
Web translates these in German and English. Native upstream error bodies and
credentials are never forwarded. Token budgeting uses a conservative character
estimate rather than exact per-vendor tokenization; later budget work must include
exact model tokenization and tool-schema overhead. Local AI HTTP network isolation
remains required; this work does not make an unauthenticated AI port public-safe.

## Verification and intentional follow-up

- Core: 222 tests and `bootJar` passed, including explicit cloud-policy denial,
  memory/history exclusion, consent audit and the existing persistence/RBAC/action
  regressions. Disposable PostgreSQL fixtures were used; no live data reset.
- AI: 163 tests passed. Cloud adapters use explicitly **simulated** HTTP transports
  for official request formats, SSE/tool normalization, usage, status errors,
  incomplete streams, timeout/cancellation, cloud gates, capabilities and API
  compatibility. Existing STT/TTS tests ran unchanged.
- Web: 140 tests passed, including simulated Core/AI chat boundaries, local
  context preservation, cloud disclosure rejection, session/CSRF and stream
  validation. TypeScript, lint and production build were run separately from dev.
- Real local Ollama: `gemma3:4b` generated `OK.` through ModelRegistry with model,
  text, usage and completion events. An initial cold-load attempt timed out; the
  bounded longer-window retry and final corrected stream completed successfully.
- No paid/live cloud test, credential provisioning, new deployment, physical Voice
  acceptance, cost enforcement or automatic fallback was performed.

Next: coordinate removal of the legacy Core voice literal; provision selected
cloud profiles; perform separately authorized synthetic-data live acceptance for
each vendor; design bounded Core-owned tool continuation and persisted usage/
spending limits. Keep runtime/kaltstart work separate from provider changes.

Official wire-format references used during implementation:
[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling),
[OpenAI streaming](https://developers.openai.com/api/docs/guides/streaming-responses),
[Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming),
[Gemini GenerateContent](https://ai.google.dev/api/generate-content),
[Gemini thought signatures](https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures).
