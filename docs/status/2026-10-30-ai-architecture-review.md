# AI architecture and multi-provider readiness review

Date: 2026-10-30. Analysis only: no provider, model routing, tool-calling engine,
or AI architecture was implemented by this review. Startup fixes belong to the
separate stabilization work. Findings come from repository code, not from an
assumption that the architecture overview describes deployed functionality.

## Current execution paths

```text
Web chat -> same-origin Next route -> Core conversation context + action interpretation
                                  -> AI chat stream -> Ollama
                                  -> Core turn completion/persistence

Voice Satellite: wake word -> VAD/capture -> authenticated Core voice session
Core -> AI transcription -> local Parakeet HTTP runtime
Core -> action interpretation OR AI chat -> Ollama
Core -> typed response plan -> AI fixed/template/dynamic audio -> local TTS
Core -> Satellite audio/playback acknowledgement -> Core-authorized execution/result
```

Core owns authorization, scoped device resolution, action policy, persistence and
audit. The Satellite captures and plays audio; it has no general device authority.
Text chat generation currently travels directly from the authenticated Next
server route to AI after obtaining context from Core. It is inaccurate to describe
all model traffic as already proxied through Core.

### AI service and models

- `services/ai/src/kyrion_ai/app.py` constructs `OllamaProvider` directly.
  `providers/base.py` has a useful `LanguageModelProvider` Protocol, but it only
  specifies `stream_chat`; application catalog, benchmark and model validation
  still depend on Ollama-specific methods. There is no provider registry/router.
- `Settings.from_environment()` reads `OLLAMA_BASE_URL`, `OLLAMA_MODEL`,
  `KYRION_ALLOWED_MODELS` and a connection timeout. Defaults are `gemma3:4b` and
  an allowlist containing `gemma3:1b`, `gemma3:4b`, `qwen3:8b`; the configured
  default is added to that allowlist. This is configuration, not proof that each
  model is installed. AI health reports configuration without testing inference.
- `/v1/models` filters Ollama tags, optionally loads metadata and reports the
  default. The Web selection persists a non-secret `kyrion-model` preference and
  submits `modelId`, checked against the service allowlist.
- Voice dialogue independently hardcodes `gemma3:1b` in
  `VoiceDialogueController.kt`; selecting a Web model does not select a voice model.
- Ollama payloads fix `num_ctx=4096`, disable thinking and use different keep-alive
  periods for text/voice. Voice output has a 256-token safety cap. These settings
  are runtime-specific and are not portable model capabilities.

### Context and memory

Core stores account-scoped conversations and turn states in PostgreSQL. The
conversation controller estimates tokens as approximately characters/4, reserves
space for selected memories and replaces older messages with a deterministic,
persisted, bounded extract. It does not ask another model to summarize. Original
messages remain in the repository; compaction is a request-context operation.

`MemoryContextSelector` chooses up to three confirmed memories from at most 100
candidates using normalized word overlap, with a higher threshold for sensitive
memories. This is explicit personal memory, not vector retrieval or a general RAG
system. `prompts.py` removes caller-supplied system messages and injects Kyrion's
instructions; memory values are quoted data. The current voice chat path sends
an empty memory list and uses its own recent conversation handling.

The context estimate does not comprehensively reserve system-prompt, future tool
schema, provider framing and output tokens. Different tokenizers and context
windows therefore need explicit budgeting before supporting other models.

### Actions and tool calling

The bounded device proposal endpoint currently uses deterministic German/English
recognition in `device_commands.py`. It does not send native function definitions
to Ollama. It returns a typed capability, selector and arguments. Core resolves
stable targets, validates capability/arguments and applies RBAC/policy/audit through
the shared Action Orchestrator and command services. This useful deterministic
path should remain available without a language model.

`ChatMessage` only supports user/assistant/system strings; `ChatEvent` only supports
message start/delta/completion/error. Neither represents a general tool call,
tool result, usage, refusal or finish reason. Some selector fields are still
provider-specific (`nanoleaf`, `zigbee`, `light`), despite the provider-neutral
direction. Native LLM tool calling requires a new bounded contract, not just
adding an API URL.

### Speech and streaming

Local STT uses an OpenAI-compatible HTTP *format* to Parakeet on 8040; this does
not mean audio is sent to OpenAI. Faster-Whisper and Piper are explicit
compatibility choices. Default TTS is the local HTTP batch runtime on 8020.
Fixed audio is checksum-reviewed; template audio uses a complete-utterance cache;
dynamic plans synthesize text through the configured speech boundary. Experimental
XTTS can fall back to Chatterbox after validating/buffering its stream. This is
speech fallback, not language-model fallback.

The Satellite has batch and opt-in PCM paths. The established dialogue path uses
NDJSON with WAV/base64 audio and playback acknowledgement; ordinary conversational
LLM text is collected before response synthesis. Repository PCM, segmentation
and experimental streaming code does not establish full-duplex production voice.

Ollama NDJSON is normalized into Kyrion NDJSON, then forwarded/persisted by Web.
Connect/status errors map to `MODEL_UNAVAILABLE`; stream/JSON errors map to
`STREAM_FAILED`. The Ollama read timeout is unlimited. Several Core AI clients
construct `RestTemplate()` without explicit connection/read deadlines. Satellite
turn requests use a 180-second timeout; STT uses 30 seconds and batch TTS 120
seconds. There is no shared end-to-end deadline or general language-model retry/
fallback policy. Truncated/malformed upstream events, cancellation, terminal
events and partial-output persistence need consistent adapter contract tests.

### Existing cloud experiments

`cloud_conversation.py` already contains an opt-in, disabled-by-default Gemini/
OpenRouter conversation spike with ephemeral sessions, bounded in-memory history
and no tools. It is separate from the normal provider Protocol, durable Core
conversation/memory and normal tool-authority path. OpenRouter's current spike
restricts requests to free-model routes. It is not a direct OpenAI or Anthropic
adapter and must not be represented as finished multi-provider support.

The AI HTTP surface itself has no general Core-to-AI authentication middleware.
Loopback/network isolation remains an important assumption. Cloud spike endpoints
must not become an unauthenticated LAN/public route or acquire device authority.

## Proposed multi-provider boundary (not implemented)

```text
Core: user/workspace policy, consent, permitted model profile, tool allowlist
      context/memory disclosure limits, budget, correlation and action ledger
                           |
AI: normalized request -> model router -> provider adapter
                              |-> Ollama (local default)
                              |-> OpenAI API (explicit opt-in)
                              |-> Anthropic API (explicit opt-in)
                              `-> later adapters
                           |
          normalized text / tool proposal / usage / terminal event
                           |
Core: validate, approve if needed, execute once, audit, return typed result
```

1. Define a versioned provider port covering generation, streaming, supported
   capabilities, optional model discovery and normalized errors. Benchmarks and
   model installation are optional capabilities, not universal provider methods.
   Keep SDK types and wire formats inside each adapter.
2. Define model profiles with stable IDs, provider/model identity, context/output
   limits, tool/schema support, modality, privacy classification and optional
   pricing/budget metadata. Separate profiles for chat, voice and bounded tasks.
   Core owns who may select a profile and external-data permission; AI resolves
   only trusted server configuration, never arbitrary browser-provided endpoints.
3. Add typed content blocks, tool definitions/calls/results, call IDs, finish
   reasons, usage and error metadata. Translate provider events into one Kyrion
   stream. Buffer/validate a complete tool proposal before Core sees executable
   intent; partial streamed arguments never authorize execution.
4. Let Core supply a least-privilege tool catalog. Native proposals and existing
   deterministic proposals feed the same target/policy/permission/audit path.
   Keep execution/correlation/idempotency state in Core. Limit tool rounds and
   parallelism; prevent a retry or fallback from replaying a completed action.
5. Add deadlines for connection, first token, idle stream and total turn; propagate
   cancellation across Web/Core/AI/runtime. Normalize timeout, rate limit,
   authentication, quota, unsupported capability, refusal and malformed response.
6. Make fallback an explicit policy. Default to local-only and no cloud fallback.
   Crossing a privacy boundary requires prior user/workspace consent and a visible
   actual provider/model result. Retry transient generation failures before output
   within a budget. After partial output, use a clearly separate attempt or error;
   never silently concatenate answers or repeat effects. Permission denials and
   validation failures are not reasons to try another model.
7. Budget the complete request with provider/model-aware estimates or token counts,
   including instructions, memories, tools and output reserve. Keep authoritative
   history local. Store any provider-specific opaque reasoning/session state in a
   separate namespace; do not assume it can be replayed across vendors.
8. Keep API keys server-side with protected configuration/credential storage.
   Minimize context exports, enforce sensitive-memory disclosure independently
   from prompt wording, show destinations, and audit metadata without raw prompts,
   recordings or secrets. Review actual account data-retention/residency settings
   before cloud acceptance; this report makes no blanket privacy guarantee.

No new queue, service, agent framework or vector database is required for this
first boundary. Existing HTTP/JSON and a small adapter registry are sufficient.

## Evidence and implementation sequence

Start with an ADR and normalized contracts plus fixtures for the *existing* Ollama
adapter. Add text-only, explicitly configured OpenAI next, then Anthropic against
the same contract suite. Add native tool proposals only after text, privacy,
timeouts and cancellation pass. Introduce optional fallback last. Preserve the
deterministic device path and Core authority throughout.

Required tests: valid/malformed streams, EOF without completion, first-token/idle/
total deadlines, cancellation, refusal, 401/429/5xx, usage normalization, model
allowlist, sensitive-memory/cloud denial, tool schema validation, unsupported
capabilities, bounded tool rounds, duplicate results and fallback after uncertain
execution. Mocked contract tests precede separately authorized, synthetic-data
live-provider acceptance. Existing device and voice physical acceptance remains.

Official references checked for adapter shape, not model recommendations:

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
  describes application-executed calls and matching results.
- [OpenAI streaming](https://developers.openai.com/api/docs/guides/streaming-responses)
  uses typed server-sent events; the adapter must map them to Kyrion events.
- [Claude tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
  has its own tool-use/result representation and client/server tool distinction.
- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling)
  supports native tool requests/results, which Kyrion's current adapter does not use.

## Technical debt and limits

Immediate priorities are reliable local startup and accepted Calendar/HA changes.
AI-specific debt is hardcoded voice model/context, split text/voice context,
unbounded reads, partial stream validation, direct Ollama application coupling,
experimental cloud lifecycle/isolation and absent cloud-disclosure policy. GPU
memory is shared by Ollama and Chatterbox; model swaps/parallel speech need a
measured resource budget. STT/TTS licenses, model artifacts and private reference
audio remain separate operational dependencies. Capability support and practical
quality require per-model evaluation, not inference from a provider name.
