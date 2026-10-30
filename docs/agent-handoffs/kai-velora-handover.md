# K-AI / Velora agent handoff

Date: 2026-10-30. Documentation-only closeout of this Codex session.
Owner/scope: AI provider foundation, orchestration, personal memory/context and
the related Velora model/context integration. No further implementation is planned
in this session. This file is independent of the other agents' handoffs.

## Assignment and ownership

The session initially received a status/startup and recovery-stabilization request,
then implementation assignments for K-AI Milestones 01, 02 and 03. The later
assignments established that recovery integration was already completed in
`3661544` and that another process owned runtime/TTS/cold-start stabilization.
Those operational/recovery changes are **not** claimed as this agent's work.

Delivered scope:

- M01: provider-neutral AI service with Ollama, OpenAI, Anthropic and Gemini;
  profiles, streaming/tool normalization, cloud controls, Core/Web integration.
- M02: Core-owned deterministic routing, preferences, administrator policy,
  usage reservations, optional controlled fallback and common Voice model choice.
- M03: central personal Context Builder, memory validity and retrieval settings,
  provenance/source inspection, bounded history/calendar retrieval and safe Voice
  handling when the speaker is unknown.

Not owned: Spaces/user-management implementation, Knowledge document ingestion,
  embeddings/PDF parsing, installer, website, LAN/firewall scripts, recovery and
  physical STT/TTS/runtime stabilization. Some commits contain contributions from
  multiple processes; a commit's title or full diff is not an attribution claim.

## Implemented components and evidence

| Area | Implemented behavior | Validation / limitation |
| --- | --- | --- |
| Providers | Ollama NDJSON, OpenAI Responses SSE, Anthropic Messages SSE, Gemini GenerateContent SSE; normalized messages/system instructions, usage, complete tool calls/results and sanitized errors | Cloud HTTP transports simulated; real Ollama generation passed; account-specific cloud acceptance not performed |
| Profiles | Operator-defined IDs, provider/model identity, explicit capabilities, locality, activation, context/output limits, deadlines and optional prices/currency | Unknown capabilities fail closed; multimodal flags are preparation, not a complete multimodal implementation |
| Routing | Pure deterministic local-first filtering/sorting; user preferences subordinate to administrator allowlists/priorities; explicit selection only when allowed | Unit/integration tested; availability comes from catalog/configuration, not paid cloud health probes |
| Policy / accounting | Personal preferences, workspace policy, per-account UTC-month usage, atomic conservative reservations, request replay protection, server-observed settlement | Concurrent reservation tests passed; uncertain attempts retain reservations; monetary values are estimates |
| Fallback | User and admin opt-in, explicit targets, same disclosure boundary, explicit availability/rate-limit errors before output only | No retry after timeout, cancellation, partial/tool output or unknown outcome; audited and separately reserved |
| Context | Existing history/summary cache plus selected confirmed memories, optional previous conversations/routing preferences/personal calendar | Deterministic bounded retrieval; token estimation is approximate; source preview is recomputed, not immutable history |
| Memory lifecycle | Existing categories/provenance/confirmation/conflict handling/CRUD retained; active flag, expiry, owner metadata and category filters added | PostgreSQL-backed checks passed; expiry excludes rather than deletes records; no automatic inference or hidden confirmation |
| Web | Provider/model selection, local/cloud visibility, routing/policy/budget settings, expanded Memory panel and source inspector; German/English resources | Tests/typecheck/build passed at recorded checkpoints; final full lint has a concurrent Knowledge error |
| Voice | Shared routing/context path; explicit Core-selected local profile; removal of legacy Core `gemma3:1b` binding | Authenticated account requests can use private context; satellite credentials identify a device, not its speaker |

### Source map

- AI: [registry](../../services/ai/src/kyrion_ai/models.py),
  [contracts](../../services/ai/src/kyrion_ai/model_contracts.py),
  [provider contract](../../services/ai/src/kyrion_ai/providers/base.py),
  [cloud adapters](../../services/ai/src/kyrion_ai/providers/cloud.py),
  [Ollama adapter](../../services/ai/src/kyrion_ai/providers/ollama.py),
  [stream transport](../../services/ai/src/kyrion_ai/providers/http_stream.py).
- Core: [router](../../services/core/src/main/kotlin/dev/kyrion/core/ai/ModelRouter.kt),
  [settings/usage](../../services/core/src/main/kotlin/dev/kyrion/core/ai/AiSettings.kt),
  [orchestration](../../services/core/src/main/kotlin/dev/kyrion/core/ai/AiOrchestration.kt),
  [gateway](../../services/core/src/main/kotlin/dev/kyrion/core/ai/AiGateway.kt),
  [Context Builder](../../services/core/src/main/kotlin/dev/kyrion/core/context/ContextBuilder.kt),
  [personal source contract/calendar](../../services/core/src/main/kotlin/dev/kyrion/core/context/PersonalContextDataSource.kt),
  [memory controller](../../services/core/src/main/kotlin/dev/kyrion/core/memory/PersonalMemoryController.kt),
  [Voice dialogue](../../services/core/src/main/kotlin/dev/kyrion/core/voice/VoiceDialogueController.kt).
- Web: `apps/web/src/features/models/`, `features/memory/`,
  `components/ai-orchestration-settings.tsx`, `memory-panel.tsx`,
  `context-source-inspector.tsx`, `app/api/ai/[operation]/route.ts`,
  `app/api/chat/route.ts`, `app/api/memory/`.
- Decisions: [ADR 0027](../adr/0027-multi-provider-ai-foundation.md),
  [ADR 0028](../adr/0028-core-owned-ai-orchestration.md),
  [ADR 0029](../adr/0029-personal-context-engine.md).
- Detailed behavior: [providers](../ai-model-providers.md),
  [orchestration](../ai-orchestration.md),
  [personal context](../personal-context-engine.md),
  [original personal memory](../personal-memory.md).

### Data flow and safety boundaries

Web validates the session/CSRF, requests Core routing and persists the user turn.
Core reloads the owned conversation, builds context, checks policy/budget, then
streams through AI to the configured provider. Usage comes from Core's upstream
stream, never browser-submitted accounting. Core remains the authorization,
confirmation, validation, device-execution and audit authority.

Providers can propose typed tools but cannot execute devices. The generation
surface does not implement a general native tool execution/continuation loop;
unexpected native tool events fail closed. Existing controlled Core actions remain
separate. Retrieved statements are quoted data, not execution authority.

Personal retrieval uses the authenticated **account ID**, not a device workspace
owner substitution. `conversations:read` is required; memory additionally needs
`personal_memories:read`; the optional personal calendar adapter requires
`calendar:read` and exact account ownership. Shared enterprise sources are not
enabled by this builder. No platform Space implementation existed in this main
checkout at the initial inspection; separate Spaces work was not integrated here.
Concurrent Knowledge collections/assembler are another workstream and must not be
mistaken for validated platform tenant isolation.

Cloud needs enabled profiles, server credentials and cloud enablement in Core/AI,
administrator allowance, personal allowance/local-only disabled and exact
provider consent per message. Only that message is released. Memories, history,
calendar and preferences remain local. No automatic local-to-cloud fallback.
Expanding disclosure needs a new explicit server policy and renewed consent.

Satellite enrollment proves device identity only. Satellite dialogue therefore
sets `personalContextAllowed=false`: only the current utterance reaches generation,
without personal history/memory/calendar/preferences/documents. The internal
Voice API defaults to this restriction. Verified account paths can opt in on the
server; no request-body flag overrides the satellite boundary. No speaker
recognition, incremental audio redesign or physical hardware acceptance is claimed.

### Database and API changes

Additive migrations owned by this work:

- V34 `ai_preferences_policy_and_usage`: `ai_user_preferences`,
  `ai_workspace_policy`, `ai_usage_attempt`; preferences/policy JSON, usage and
  estimated cost counters, pending/uncertain states and unique actor/request/attempt.
- V35 `personal_context_controls`: existing `personal_memory` gains `active` and
  `expires_at` plus an index; existing `owner_memory_settings` gains history,
  preferences and category controls. Confirmed records are preserved.
- V37 `personal_calendar_context_opt_in`: adds `kyrion_data_enabled` to those
  settings. V36 belongs to concurrent Knowledge work, not this agent.

Core `/v1/ai`: GET/PUT `preferences`, GET/PUT `policy`, GET `usage`, POST `route`,
POST `chat/stream` (NDJSON). Personal operations use conversation permissions;
policy uses `system_settings:read/update`. API parsing rejects unknown fields,
coerced privacy booleans, null primitives and trailing JSON.

Existing `/v1/memory` CRUD/confirmation remain. Additions: PUT `context-settings`,
PATCH `/{id}/validity`, POST `/{id}/reject`, GET `context` with owned conversation
and turn IDs. Existing memory permission mapping applies. Rejection deletes only
an explicitly selected owned proposal and records a rejection audit event.
Same-origin Web routes retain session/CSRF and Core ownership enforcement.

AI retains `/v1/models` and `/v1/chat/stream`; catalog metadata includes profiles,
providers and `voiceProfileId`. Streams retain existing message events and add
model/usage/tool metadata. Core now supplies actual generation memory/compaction
metadata; Web does not substitute the earlier preview's memory selection for it.

### Fixes made during the session

Corrected prematurely nested Python streaming/completion control flow; bounded
incomplete/error stream handling; aligned Python EditorConfig indentation with
Ruff; added Core HTTP total-deadline/cancellation coverage; delayed successful
completion until usage settlement; bounded metadata buffering; rechecked policy
before fallback; made expiry parsing explicit without assuming a Jackson time
module; prevented stale/expired/inactive memory selection; distinguished satellite
device identity from personal speaker identity. Runtime/TTS/PostgreSQL startup
repairs performed by other processes are not included in this list.

## Verification record

Historical checkpoints are not guarantees about the current concurrently changing
HEAD. No suites, cloud calls, builds or runtime restarts were repeated for this
documentation-only closeout.

| Checkpoint | Core | AI | Web |
| --- | --- | --- | --- |
| M01 | 222 tests and bootJar passed | 163 tests passed | 140 tests, typecheck/lint/build passed |
| M02 (`36e0af2`) | 236 tests, zero failures/errors/skips; bootJar passed | 164 tests, Ruff/changed-file formatting/compilation passed | 152 tests, TypeScript/ESLint/build passed |
| Final M03 scoped validation | 18 selected tests, zero failures/errors/skips; bootJar passed | 166 tests, Ruff and compilation passed; count includes concurrent Knowledge tests | 159 tests and TypeScript passed; production build passed; changed Memory/Context lint passed |

The final scoped Core run includes database-backed context/history/expiry/category
and account-isolation checks, memory validity/rejection, verified versus unverified
Voice context, existing cloud policy, router, strict input and HTTP transport tests.
Relevant files: `AuthenticationPersistenceIntegrationTest.kt`,
`CloudContextPolicyTest.kt`, `ai/ModelRouterTest.kt`, `AiConfigurationInputTest.kt`,
`HttpAiGatewayTest.kt`; AI `tests/test_multi_provider.py`, `test_contracts.py`;
Web `features/memory/context-contracts.test.ts`,
`app/api/memory/context-settings/route.test.ts`, `app/api/ai/[operation]/route.test.ts`
and `app/api/chat/route.test.ts`.

Full M03 checks were **not all green**:

- An isolated Core run completed 239 tests with one failure:
  `additive migration closes bootstrap on an existing V30 installation and preserves grants`.
  Concurrent V36 adds Knowledge grants to existing roles; the original unchanged-
  grants assertion fails. This agent did not change that policy or weaken the test.
- A later full run had an authentication-fixture PostgreSQL Testcontainers startup
  timeout and two new Knowledge integration failures: cleanup/recoverability and
  persisted answer references. Initial overlapping build outputs also produced
  class-not-found failures; subsequent scoped runs used isolated output.
- Full Web lint failed in concurrently added `knowledge-view.tsx` for React
  `set-state-in-effect`. Memory/Context lint passed after fixing its own render-time
  clock usage. No claim that the entire current repository passes lint/tests.

Real runtime evidence: local `gemma3:4b` returned `OK.` through ModelRegistry with
model/text/usage/completion events. One cold-load attempt needed a longer bounded
window. This is provider evidence, not full HTTP end-to-end or physical Velora
acceptance. Cloud tests were explicitly simulated; no billable cloud requests.

Commands used (run later only when resuming development):

```powershell
# Repository root; Java 21 required
$env:JAVA_HOME='<local-JDK-21-directory>'
.\services\core\gradlew.bat -p services/core test bootJar --console=plain '-Pkotlin.compiler.execution.strategy=in-process' '-Pkotlin.incremental=false'
# services/ai
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m compileall -q src
# apps/web
pnpm test
pnpm exec tsc --noEmit
pnpm lint
$env:KYRION_BUILD_DIRECTORY='.next-kai03-build'
pnpm build
```

The isolated Core build used an ignored `.run/kai03/isolated-build.gradle` init
script setting `layout.buildDirectory` to `.run/kai03/core-build` and disabling
the parallel Knowledge scheduled worker in test JVMs. It used a separate project
cache and disposable PostgreSQL containers. The final `test` filters selected
`*AuthenticationPersistenceIntegrationTest.*context*`, `*...*memory*`,
`*AuthenticationPersistenceIntegrationTest.voice uses the central*`,
`*CloudContextPolicyTest`, `*ModelRouterTest`, `*AiConfigurationInputTest` and
`*HttpAiGatewayTest`. Put `--tests` options immediately after `test`, before
`bootJar`. This local init script is not a checked-in release configuration.

## Configuration and operations

Required services: Core/PostgreSQL, AI, Web and Ollama for local generation;
Parakeet/Chatterbox and the enrolled satellite only for physical Voice acceptance.
This agent did not change Docker/runtime ownership or deploy these migrations.
The actual live database's applied migration state was not inspected at closeout.

- AI: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `KYRION_ALLOWED_MODELS`, optional
  `KYRION_MODEL_PROFILES_FILE`; see `services/ai/model-profiles.example.json`.
- Optional cloud: `KYRION_AI_CLOUD_ENABLED` in Core **and** AI;
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` in protected AI process
  environment only. Model IDs/capabilities/prices/currency are operator-configured;
  no vendor prices are assumed. Profile JSON contains metadata, never keys.
- Core AI endpoint: `KYRION_AI_BASE_URL`; Web server endpoints:
  `CORE_SERVICE_URL`, `AI_SERVICE_URL`. Keep local AI/Ollama ports private; they
  are not made public-safe by these changes. Preserve existing database, audit,
  credential-protection and bootstrap configuration from the startup guide.
- AI has no implicit dotenv loading in `Settings`; the trusted launcher must
  supply its environment (or an explicit uvicorn env-file). Cloud credentials
  were neither provisioned nor validated against real accounts here.
- Budget defaults are local-only/no fallback. Monetary-limited requests fail
  closed with unknown pricing/currency, including unpriced local profiles.

For the next authorized runtime start, follow [development startup](../development-startup.md).
Existing entry points are Core `gradlew.bat bootRun` from `services/core`, AI
`.venv\Scripts\python.exe -m uvicorn kyrion_ai.app:app --host 127.0.0.1 --port 8000`
from `services/ai`, and `pnpm dev` from `apps/web`. Web's dev command can start
the existing recovery helper; it is not a production deployment command. Before
starting Core, review pending migrations with the other workstreams and establish
a verified backup/restore point. Do not reset the database or overwrite secrets.

## Cross-agent dependencies and Git state

Shared hot spots: `AiOrchestration.kt`, `ConversationController.kt`,
`VoiceDialogueController.kt`, `AuthenticatedRouteInterceptor.kt`,
`AuthenticationPersistenceIntegrationTest.kt`, AI `contracts.py/models.py/prompts.py`,
Web chat route/contracts/transport/view and `app-shell.tsx`; migration ordering and
role grants are shared integration contracts. Coordinate edits, especially when
Knowledge adds sources outside ContextBuilder or Spaces changes identity scope.

Integration order: agree on a common source revision and ownership boundaries;
review V34/V35/V36/V37 and role policy; verify backup/restore and additive upgrade;
run all coordinated checks; only then authorize runtime/hardware/cloud acceptance.
Do not integrate unreviewed Space or Knowledge permission changes merely to make
tests pass. No new branches/worktrees or migration edits are part of this closeout.

Reference commits: `ecf1a38` (M01 final stream correction), `36e0af2` (M02 closeout),
`29209c0` (orchestration docs), `5125f71` (expiry metadata), `f2da1d9` (M03 final
Voice/context restriction and evidence). Feature work is distributed over earlier
shared commits; `f2da1d9` also includes unrelated LAN files committed concurrently,
which are not this agent's work. Do not cherry-pick a mixed commit blindly.

At closeout inspection, HEAD was `f2da1d9`. The worktree had dirty nested
`.worktrees/calendar-ha-recovery`, `.worktrees/k-data-m01`, `.worktrees/kyrion-spaces`,
and staged `infrastructure/dev/Activate-CoreLan.ps1` / `Probe-VoiceTurn.py` from
other workstreams. No uncommitted AI/Memory/Context implementation files remained.
This new handoff is the only intended documentation-closeout addition. Other
agents may change Git state while it is being written; preserve their index and
files. Commit only this file with an explicit path, never `git add .` or a blanket
commit. The final handoff commit is reported in the session closeout message.

## Open TODOs

12 open items: **P0: 0, P1: 6, P2: 5, P3: 1**. No item is complete merely because
code exists. A newly demonstrated authorization bypass would escalate to P0;
the known permission-migration discrepancy currently requires review, not an
unsupported claim that a data leak has already been demonstrated.

### KAI-001 — Establish a coordinated passing integration baseline
- Priority: P1. Components: Core, Web, Knowledge, migrations, shared CI/build output.
- Problem/state: final whole-repository tests/lint are not green; see exact failures above.
- Next: review V36 grant intent with its owner; resolve upgrade-test expectation or policy explicitly; fix Knowledge integration/lint issues; isolate build output and repeat all suites once on a fixed revision.
- Dependencies: Knowledge and stabilization agents; sufficient local Docker resources.
- Acceptance: full Core/AI/Web tests, typecheck, lint and builds pass with recorded revision; no weakened ownership/grant checks.
- Risks: hidden privilege expansion, racing compiled classes, mistaking scoped success for release validation.

### KAI-002 — Validate the additive operational upgrade
- Priority: P1. Components: PostgreSQL/Flyway, Core, installer/runtime.
- Problem/state: V34/V35/V37 tested on disposable databases; live applied state and rollout not verified by this agent; V36 is an interleaved dependency.
- Next: inventory applied versions read-only, verify a restorable backup, review ordered migrations and existing-account fixtures, then plan an authorized upgrade.
- Dependencies: KAI-001; installer/stabilization; operator-owned backup/configuration.
- Acceptance: existing users, grants, conversations, confirmed memories and settings survive an upgrade/restore rehearsal; no reset or secret overwrite.
- Risks: checksum/order conflicts, accidentally applying unreviewed parallel migrations, irrecoverable operational changes.

### KAI-003 — Verify physical Velora and trustworthy personal identity
- Priority: P1. Components: satellite/session identity, Core Voice, Web Voice, STT/TTS runtime.
- Problem/state: shared routing/context is software-tested; device identity is not speaker identity, so satellites intentionally use current-utterance-only context. Physical acceptance is unperformed.
- Next: first test safe current-only behavior on hardware, then design an explicit trusted account/speaker binding before enabling personal context; test session cancellation and cross-user changes.
- Dependencies: stabilization/Voice owner, hardware access; future identity/Spaces decisions.
- Acceptance: unknown speakers never receive owner/other-user history or memories; verified sessions use only their allowed context; wake/STT/TTS/playback and cancellation pass physically.
- Risks: voice disclosure in shared rooms, stale identity/session reuse, claiming authenticated hardware implies authenticated speaker.

### KAI-004 — Approve and validate real cloud provider configurations
- Priority: P1. Components: AI adapters, Core cloud policy, Web model consent.
- Problem/state: adapters implemented and mocked; no live OpenAI/Anthropic/Gemini account/model/key validation or paid request occurred.
- Next: operator provisions current supported model profiles/credentials; obtain explicit spending/test approval; run minimal synthetic-data streaming/tool/usage/error acceptance for each provider.
- Dependencies: KAI-001; protected server credentials, provider accounts and spending authorization.
- Acceptance: real configured models work; consent/local-only/admin restrictions and history/memory exclusion hold; no credentials in browser/logs.
- Risks: API/model drift, paid calls, accidental personal-data disclosure; configuration alone is not live availability evidence.

### KAI-005 — Reconcile uncertain usage and assess budget guarantees
- Priority: P1. Components: AiUsageService, usage tables, admin budget UI.
- Problem/state: reservations and reported usage work; pending/uncertain attempts stay charged and there is no trusted reconciliation workflow. Estimates are not exact billing guarantees.
- Next: define auditable operator reconciliation and crash recovery; verify late/missing provider usage, concurrent accounting, model pricing/currency validation and monthly boundaries.
- Dependencies: KAI-004 for live provider evidence; Core account/audit ownership.
- Acceptance: recovery cannot double-charge/refund/replay requests; unknown outcomes remain conservative; UI clearly separates reported usage and estimates.
- Risks: permanently exhausted budgets, inaccurate cost estimates, unsafe refunds or retries after uncertain outcomes.

### KAI-006 — Integrate authoritative Spaces without weakening personal isolation
- Priority: P1. Components: ContextBuilder, RBAC, Spaces identity, calendar and Knowledge source adapters.
- Problem/state: personal account isolation is tested; enterprise retrieval is not implemented/validated here. Parallel Knowledge collections are not a proven platform tenant boundary.
- Next: review the actual Spaces result with its owner; propagate a server-derived scope and permission contract; test personal/household/business separation before adding shared sources.
- Dependencies: Spaces/user-management and Knowledge handoffs; KAI-001.
- Acceptance: cross-space/user negative tests pass in Core and Voice; no workspace-owner or client-selected tenant substitution; model-instance sharing grants no access.
- Risks: household/business mixing and implicit grants during integration. Do not enable enterprise context before this gate.

### KAI-007 — Persist immutable per-generation context selection evidence
- Priority: P2. Components: Context Builder, generation/audit persistence, Web source inspector.
- Problem/state: selected sources and actual memory metadata are visible; preview recomputes current data and does not reconstruct a historical answer exactly.
- Next: define minimized source IDs/revisions/reasons and retention rules; persist them with generation correlation; make inspection explicitly distinguish actual versus preview.
- Dependencies: KAI-005/KAI-006 and Knowledge answer-source contracts.
- Acceptance: an answer's selected sources can be explained after edits/deletion without retaining unnecessary sensitive text; ownership/deletion semantics tested.
- Risks: stale provenance, excessive personal-data retention, exposing foreign source identifiers.

### KAI-008 — Calibrate context/token budgeting
- Priority: P2. Components: ContextBuilder, AI profile validation, provider token metadata.
- Problem/state: bounded deterministic character estimates and known context/output limits work; exact tokenizers and complete vendor/tool overhead accounting are absent.
- Next: evaluate multilingual/long/tool-heavy inputs; add measured tokenizer/overhead support only where justified; retain a safe unknown-model limit.
- Dependencies: KAI-004 and operator model metadata; KAI-005 accounting.
- Acceptance: stress cases stay within declared model windows or fail clearly without losing the current message; no silent cloud escalation.
- Risks: undercounting multilingual input, conservative false rejections and context loss.

### KAI-009 — Complete memory lifecycle/backup acceptance
- Priority: P2. Components: personal_memory/settings, existing backup/retention APIs, Memory UI.
- Problem/state: confirmation, CRUD, expiry exclusion and proposal rejection are tested; expiry does not erase records and backup/restore of newly added controls has not been validated here.
- Next: test additive backup/export/import with validity/context settings; define expiry versus deletion semantics and explicit sensitive-memory retention UX.
- Dependencies: installer/backup/retention owners and KAI-002.
- Acceptance: restored confirmed memories/settings remain correct; deleted/expired records obey documented policy and never silently re-enter context.
- Risks: restoring stale sensitive memories, losing user opt-outs, treating exclusion as deletion.

### KAI-010 — Evaluate retrieval quality and consolidate source integration
- Priority: P2. Components: lexical history/memory selection, personal calendar, Knowledge integration.
- Problem/state: bounded deterministic selection works; relevance evaluation is limited. Parallel document assembly lives outside this builder and is not claimed as this agent's completed source integration.
- Next: build small DE/EN relevance fixtures; test sensitive/irrelevant prompts and source priority; agree on one scoped budget/provenance contract for additional adapters.
- Dependencies: KAI-006/KAI-007 and Knowledge owner; do not introduce a competing store/vector service.
- Acceptance: relevant sources are selected consistently, irrelevant/sensitive sources excluded, total budgets and provenance remain correct across adapters.
- Risks: over-retrieval, prompt injection from quoted data, duplicate context and inconsistent source disclosures.

### KAI-011 — Implement a separately reviewed native tool continuation loop
- Priority: P2. Components: normalized AI tool contracts, Core action execution/idempotency/audit.
- Problem/state: provider tool calls/results normalize correctly; generic generation does not execute/continue arbitrary native tool calls. Existing deterministic Core actions remain available.
- Next: define bounded Core-owned execution/confirmation/results, strict schema and permission checks, idempotency keys and cancellation/unknown-outcome handling before enabling it.
- Dependencies: existing action subsystem, KAI-001/KAI-004; administrator security review.
- Acceptance: every execution is authorized/audited, critical actions confirmed, duplicates and unsafe fallback prevented; prompt content cannot grant authority.
- Risks: double execution, confused deputy, retries after unknown device outcomes.

### KAI-012 — Improve configuration and source-inspection ergonomics
- Priority: P3. Components: model catalog, Memory/Context settings and error localization.
- Problem/state: current controls and linked-turn inspector work; live provider health, richer relevance explanations and general conversation-source browsing remain limited.
- Next: expose clear configured-versus-live status without automatic paid probes; improve explanations/navigation using existing UI conventions.
- Dependencies: KAI-004/KAI-007/KAI-010.
- Acceptance: DE/EN UX explains blocked sources, selected model and estimate limitations without exposing credentials or private foreign metadata.
- Risks: misleading availability labels or unnecessary background provider requests.

## Current State

1. Proven: local Ollama streaming; M01/M02 checkpoint suites; final scoped Core
   Context/Memory/privacy/Voice tests; recorded AI/Web tests and builds; explicit
   cloud gating, account isolation and satellite personal-context denial.
2. Implemented but not fully accepted: live cloud models, production migration
   upgrade, physical Velora, exact costs/token windows and combined cross-agent
   release behavior. Enterprise/document integration is not completed by this agent.
3. Not working at last observed whole-repository validation: the V30 upgrade/grant
   preservation regression with concurrent V36; full Knowledge integration checks;
   full Web lint in `knowledge-view.tsx`. Testcontainer startup was also flaky.
4. Main risks: concurrent shared-file changes, unreviewed role grants, uncertain
   usage accounting, speaker-versus-device identity and unvalidated Space integration.
5. First resume check: read all handoffs, inspect current Git/index/worktrees and
   migration history without changing them, agree on a stable integration revision,
   then address KAI-001/KAI-002. Do not assume historical green counts certify HEAD.

## Recommended Next Steps

1. Resolve and validate the combined Knowledge/RBAC/test/lint integration baseline.
2. Rehearse backed-up additive database upgrade and restore with existing accounts.
3. Physically accept safe Velora and establish trusted identity before personal satellite context.
4. Reconcile uncertain usage, then perform explicitly approved synthetic cloud acceptance.
5. Integrate authoritative Spaces and immutable source provenance before shared enterprise retrieval.

No new feature implementation, migration modification, regression run, paid API
request, service restart or productive deployment was performed for this closeout.
