# K-AI Milestone 02: Core-owned orchestration

## Implemented request path

Web authenticates the session and checks CSRF, obtains a routing preview from
Core, and creates the conversation turn through the existing API. Device intents
still pass through the existing Core action interpreter and execution policy.
Language generation now streams Web → Core → AI → configured provider. Core
reloads the owned conversation and constructs context itself; browser-supplied
history, memories, prices and usage counters are not authoritative inputs.

The deterministic router filters configured profiles by availability, enabled
state, administrator provider/profile allowlists and required capabilities.
Unknown capabilities are unsupported. Explicit selections require administrator
permission. Automatic selection orders local profiles first, then task-specific
and global administrator priorities, personal chat/voice profile and provider
preferences, optional configured input-price ordering, the configured default,
and finally profile ID. Budget feasibility is enforced transactionally before
generation; it does not silently choose another model when a budget is exceeded.
The routing response includes the decision reason, rejected profiles and allowed
fallbacks. There is no intent-classifier model or hidden billable routing call.

## Configuration and permissions

Migration `V34__ai_preferences_policy_and_usage.sql` adds preferences, workspace
policy and usage tables. Existing accounts, conversations and model configuration
are preserved. This migration has been exercised against disposable test
PostgreSQL, not applied to the running platform by this work.

Authenticated Core endpoints:

| Endpoint                  | Permission / purpose                                                  |
|---------------------------|-----------------------------------------------------------------------|
| GET `/v1/ai/preferences`  | `conversations:read`; personal settings and effective policy          |
| PUT `/v1/ai/preferences`  | `conversations:update`; own preferences only                          |
| GET/PUT `/v1/ai/policy`   | `system_settings:read/update`; workspace administrator policy         |
| GET `/v1/ai/usage`        | `conversations:read`; own current UTC-month usage                     |
| POST `/v1/ai/route`       | `conversations:create`; deterministic selection preview               |
| POST `/v1/ai/chat/stream` | `conversations:create`; owned turn, reservation and NDJSON generation |

The existing model settings page now contains personal preferences, administrator
controls and usage/budget information in German and English. Select Automatic to
apply routing preferences; explicit profile selection remains available when
allowed. The chat task selector supports chat, analysis and code. The display
shows the actual processing model and any controlled fallback.

Defaults allow Ollama only, enable local-only personal processing and disable
fallback. Cloud requires all of: server enablement in Core and AI, credentials
and an enabled profile in AI, administrator allowlists/cloud permission, personal
cloud permission with local-only disabled, and confirmation of the exact provider
for the current message. Automatic selection without a provider-specific consent
never escalates to cloud. Only the current user message can leave the local
boundary; history and personal memories cannot be enabled for cloud by policy.
Credentials remain server-side; no new credentials or live cloud calls were made.

## Voice

Velora's Core dialogue service uses the same router and usage accounting. Personal
voice preference takes precedence over the catalog's `voiceProfileId`, then a
safe eligible local default is selected. AI honors an explicit Core-selected
local voice profile, rejects cloud voice and publishes its default voice profile
in the catalog. The former Core `gemma3:1b` literal is removed.

Active session validation occurs on streamed events. Provider streams close on
callback failure/cancellation and bounded deadlines apply. Voice currently
collects the model text before the existing TTS response, preserving wake word,
STT, synthesis and playback behavior. Incremental audio and physical satellite
acceptance are separate work; this milestone does not claim them.

## Usage and budgets

Each attempt reserves estimated input tokens (serialized UTF-8 context bytes plus
bounded protocol overhead) and configured maximum output tokens. This is a
conservative estimate, not a vendor tokenizer. Reservations serialize with
workspace policy changes and other requests. The stricter of personal and admin
monthly token ceilings applies, alongside per-request and monetary ceilings.
Replay of an already reserved turn/attempt is rejected.

Core observes provider token metadata directly. Successful requests with known
usage settle to reported counters; incomplete, disconnected or unknown outcomes
retain conservative reservations. Usage records distinguish reported, estimated,
pending and uncertain attempts. Cost figures are explicitly estimates using only
operator-configured input/output prices and currency, never assumed vendor
prices. A monetary-limited request with unknown pricing or mismatched currency
fails closed, including a local profile without configured cost metadata.

There is no exchange-rate conversion, provider billing reconciliation or exact
hard monetary guarantee. Conservative estimates may reject short requests;
pending attempts after a crash need operator investigation. There is deliberately
no client endpoint that can refund usage or submit trusted token totals.

## Fallback and action safety

Both administrator and user must opt in, and the administrator must list allowed
fallback profiles. Only explicit availability/rate-limit errors before text or
tool output qualify. Fallback remains local-to-local or within the same explicitly
consented cloud provider. Timeouts, cancellation, malformed/truncated streams,
unknown execution outcomes and partial responses never retry. Policy and budgets
are rechecked for every attempt, with separate usage and audit records.

Model events never execute devices. Native tool events on this generation surface
fail closed; existing deterministic Core action authorization, confirmation,
execution and audit remain authoritative. A general provider-native multi-turn
tool execution loop is still follow-up work.

## Verification

Core unit and disposable PostgreSQL integration tests cover routing, preferences,
administrator overrides, cloud gates, capability filtering, concurrent budget
reservations, replay protection, usage settlement, voice selection, controlled
fallback, partial-output safety, timeouts, cancellation and policy revocation.
AI tests cover all four existing provider contracts; cloud transports are
explicitly simulated. Web tests cover session/CSRF and Core routing/generation
boundaries. The real local `gemma3:4b` provider produced `OK.` with model, text,
usage and completion events. No paid cloud acceptance was performed.

Final verification on 2026-10-30: Core **236 tests**, zero failures/errors/skips,
and `bootJar` passed; AI **164 tests**, Ruff lint, changed-file formatting and
Python compilation passed; Web **152 tests**, TypeScript, ESLint and the Next.js
production build passed. Web build output used `.next-kai02-build` to preserve
the running development output. Cloud cases used synthetic transports only.
EditorConfig now specifies four-space Python indentation to agree with Ruff.
Known non-failing warnings include Jackson/Spring deprecations and the existing
Starlette TestClient/httpx deprecation.

Run Core tests/bootJar, AI pytest/Ruff and Web tests/typecheck/lint/build before
release. See [ADR 0028](adr/0028-core-owned-ai-orchestration.md). Operational
rollout, physical Voice acceptance, uncertain-reservation reconciliation and
separately authorized live cloud acceptance remain next steps.
