# K-Data M01 agent handover

Documentation-only closeout, 2026-10-30. Technical documentation remains in English
under the repository language policy. This file belongs to the K-Data agent.

## Scope and attribution

The original assignment was **K-Data Milestone 01: Shared Knowledge Foundation +
Secure Personal RAG**: personal PDF/text upload, local ingestion and embeddings,
authorized retrieval through existing K-AI, references, download/deletion, minimal
bilingual Web UI, deployment configuration, security tests and documentation.
Organization search, cloud embeddings, OCR, a second chatbot and replacement
Voice infrastructure were explicitly excluded.

This session authored the initial knowledge slice and subsequently isolated its
completion/security changes. Concurrent activity committed some initial files
while they were being written in the shared checkout. Commit authorship alone
therefore does not identify agent responsibility. This agent does **not** claim
the pre-existing K-AI router, authentication/RBAC, personal-memory/context engine,
Spaces, LAN/firewall recovery, calendar, Home Assistant or audio pipeline as its
work. Small integration edits to those existing boundaries are described below.

The authoritative tested snapshot for this handover is:

- Branch: `feat/k-data-m01`.
- Existing worktree: `E:/dev/Kyrion/kyrion/.worktrees/k-data-m01`.
- Completion commit: **`25b6fee6402f961123cd02a633ed899ef3aa3363`**.
- Branch base: `4217ee2`; reconnaissance initially started at `ff07704`.
- Worktree was clean at closeout inspection. No new branch/worktree was created
  for this documentation task.

The shared checkout was at `74b2f66` on `refresh/product-credibility` when inspected.
It had unrelated modifications in `infrastructure/dev/Probe-VoiceTurn.py` and the
calendar/Spaces worktrees. These were neither changed nor committed here.
Later parallel changes are outside the validation claims below.

## Existing documentation and source map

- [Architecture decision](../adr/0030-personal-knowledge-foundation.md).
- [K-Data developer/operations guide](../k-data.md). Read its version at
  `25b6fee` when reproducing this agent's tested snapshot.
- [Original completion report in the existing feature worktree](../../.worktrees/k-data-m01/docs/status/2026-10-30-kdata-m01.md).
  Alternatively use `git show 25b6fee:docs/status/2026-10-30-kdata-m01.md`;
  the shared checkout did not contain that report at closeout.
- [Database backup guide](../postgres-backup-and-restore.md); this agent added
  the requirement to back up original files alongside database metadata.

Source paths below are repository-relative **at `25b6fee`**, not a claim that
later shared-checkout versions are identical:

| Component | Files and responsibilities |
| --- | --- |
| Domain | `services/core/src/main/kotlin/dev/kyrion/core/knowledge/domain/Knowledge.kt`: personal/organization ownership enum, document/job/chunk/source models and stable failure codes |
| Application | `knowledge/application/KnowledgeService.kt`: personal spaces, uploads, lifecycle, authorization, search and audit |
| Storage | `knowledge/storage/KnowledgeObjectStore.kt`: configurable local root, UUID keys, bounded atomic writes, safe paths, deletion and orphan sweep |
| Ingestion | `knowledge/ingestion/KnowledgeText.kt`, `KnowledgeWorker.kt`, `LocalEmbeddings.kt`: strict text decoding, PDF extraction, normalization, chunking, leased jobs and local embedding batches |
| PDF process | `services/core/src/main/java/dev/kyrion/core/knowledge/ingestion/PdfParserMain.java`: separate PDFBox JVM, packaged by Core Gradle/Docker configuration |
| Persistence | `knowledge/persistence/KnowledgeRepository.kt`, `KnowledgeAnswerSources.kt`: JDBC state/jobs, atomic publication, authorized cosine retrieval and saved answer references |
| API/context | `knowledge/api/KnowledgeController.kt`, `context/KnowledgeContextAssembler.kt`: API validation and bounded authorized provenance |
| Existing K-AI integration | `ai/AiOrchestration.kt`, security interceptor/RBAC, and a named-argument adaptation in `voice/VoiceDialogueController.kt` |
| Python AI | `services/ai/src/kyrion_ai/{contracts,prompts,models,app}.py`: typed excerpts, source-data separation and cloud-context rejection |
| Web | Knowledge page, `components/knowledge-view.tsx`, existing chat/shell, `features/knowledge/*`, chat contracts/transport/API, `/api/knowledge/[...path]` proxy |
| Runtime | Core `build.gradle.kts`, `Dockerfile`, `application.yml`; node/installer Compose, installer directory setup and environment template |

## Implemented behavior and data flow

The implemented personal slice is:

1. Existing authentication supplies the actor; the client never establishes ownership.
2. The actor creates their single personal space and uploads PDF or UTF-8 `.txt`.
3. Core validates type/name/size/content, writes the randomized original atomically,
   validates extraction and transactionally creates document metadata plus a job.
4. A persistent worker claims a fenced lease, extracts/normalizes/chunks text,
   requests local embeddings and atomically publishes the complete revision as READY.
5. Existing chat receives optional `knowledgeEnabled`, false by default. Existing
   model/permission/consent checks precede retrieval. Knowledge requests require local
   generation; authorized SQL search supplies bounded excerpts to the existing router.
6. AI receives excerpts as quoted untrusted JSON, outside its trusted system prompt.
   Core-generated source events carry the assistant message ID. Completed answers save
   references; originals remain available through authenticated downloads.
7. Deletion first tombstones the document, immediately excluding it from new retrieval
   and publication. Cleanup retries file/index removal; orphan files age out separately.

Additional completion fixes made by this agent:

- Corrected overbroad initial migration grants after the existing upgrade test exposed
  a regression. Final branch grants derive from each role's personal-memory operations;
  deliberately restricted roles retain restrictions. New ADMIN roles receive no
  automatic personal-data grants; ownership checks apply regardless of role.
- Rechecked source access before provider execution, enforced stream message/source
  association and persisted completed-answer references.
- Avoided conflicting job/document lock ordering by separating claim from the fenced
  document PROCESSING transition; fenced renewal/publication remain mandatory.
- Bounded actual PDF Writer output and parser concurrency, added an embedding response
  body deadline and preserved actionable embedding errors through chat to localized UI.
- Fixed this slice's Web effect lint issue. Did not fix unrelated personal-memory code.

### Migration and ownership boundary

`services/core/src/main/resources/db/migration/V36__personal_knowledge.sql` adds:

- `knowledge_spaces`: canonical `user_account` FK, personal-only DB ownership,
  immutable ownership trigger. ORGANIZATION is only a reserved domain enum.
- `knowledge_documents`: space/uploader FKs, private storage metadata, ingestion
  revision/state/error/timestamps and deletion tombstone.
- `knowledge_chunks`: revision/order/content/page/normalized offsets, model ID,
  dimension and PostgreSQL `REAL[]` vectors.
- `knowledge_ingestion_jobs`: persistent attempts/schedule/lease/failure state.
- `knowledge_answer_sources`: actor/conversation/message/document reference mapping.
- Supporting constraints/indexes and `knowledge:read/create/delete` permissions.

No canonical organization table was available in this agent's checkout; no duplicate
organization schema was invented. PostgreSQL 17 Alpine lacks the required pgvector
deployment contract, so M01 uses exact cosine search over an authorization-materialized
SQL candidate set. This alternative is implemented, not a retrieval placeholder.

### APIs and security

Core prefix `/v1/knowledge`; same-origin Web proxy `/api/knowledge`:

| Method | Suffix | Contract |
| --- | --- | --- |
| GET / POST | `/spaces` | Actor's personal list / idempotent creation |
| GET / POST | `/spaces/{id}/documents` | Bounded limit/offset listing / multipart `file` upload |
| GET | `/documents/{id}` | Safe metadata; no vector or storage key |
| GET | `/documents/{id}/content` | Protected original attachment, no-store/nosniff |
| DELETE | `/documents/{id}` | Immediate tombstone followed by cleanup |
| POST | `/documents/{id}/reindex` | New revision and durable queue entry |
| POST | `/search` | `spaceIds`, bounded query and result count; excerpts with provenance |
| GET | `/answers/{conversationId}` | Actor-scoped saved references |

`knowledgeEnabled` extends the existing AI request. `knowledge.sources` adds an
NDJSON event with `messageId` and source items; references are
`kd:documentId:revision:chunkIndex`. The normal streaming contract is retained.
Foreign documents/spaces return the same 404 as missing resources. Search scopes
ownership before ranking, rather than filtering unauthorized context afterward.
Global OWNER/ADMIN permissions do not bypass personal ownership. Web uses existing
session and CSRF handling, never browser-supplied backend credentials.

Embedding is a separate local-only capability; it never selects a chat model or
falls back to cloud. Retrieved data cannot alter Core routing, consent, identity
or tool policy. Existing current-message cloud consent does not release documents.
Prompt tests demonstrate data/instruction separation, not universal LLM obedience.
Velora's shared Core orchestration accepts the optional flag, but satellite session
controls and a physically verified voice-RAG workflow were not implemented here.

## Verification evidence

These are **historical results at the feature snapshot**, reused for this closeout.
No test suites, provider requests, service restarts or deployments were performed
for the documentation task.

| Command/check | Recorded result |
| --- | --- |
| Core: `gradlew.bat test bootJar --console=plain` with Java 21 | **252 passed**, zero errors/failures/skips; application and parser jars built |
| Core PostgreSQL/Flyway tests | Disposable PostgreSQL 17; fresh schema and V30 upgrade preservation passed |
| Web: `pnpm test` | **162 passed** |
| Web: `pnpm exec next typegen`, `pnpm exec tsc --noEmit` | Passed |
| Web: `KYRION_BUILD_DIRECTORY=.next-kdata-build pnpm build` | Production build passed |
| Web: `pnpm exec eslint` over milestone chat/knowledge/shell/proxy files | Passed |
| Web: `pnpm lint` | Failed at branch's inherited `memory-panel.tsx:171`, render-time `Date.now()` purity rule |
| AI: `.venv/Scripts/python.exe -m pytest -q` | **166 passed**, existing Starlette/httpx deprecation warning |
| AI: Ruff check/format on changed files | Passed |
| Kotlin/Java IDE formatting; `git diff --check` | Invoked/passed; no separate configured Gradle formatter/linter |
| Installer: Python unittest discovery in `infrastructure/installer-v1/tests` | **3 passed** |
| `docker compose -f <file> config --quiet` | Development, node and installer Compose passed using non-secret validation placeholders |

Relevant test files: Core `knowledge/KnowledgeSecurityIntegrationTest.kt` and
`KnowledgeLocalComponentsTest.kt`, existing
`security/AuthenticationPersistenceIntegrationTest.kt`; AI
`tests/test_knowledge_context.py`; Web `features/knowledge/contracts.test.ts` and
`app/api/knowledge/knowledge-proxy.test.ts`.

Coverage includes cross-user/admin denial, deletion during embedding, expired-worker
fencing, competing claims, restart recovery, failed-ingestion invisibility, revision
and dimension separation, actual PDF parsing/rejection, traversal/size/UTF-8 checks,
local embedding adapter errors, no cloud fallback, source association/persistence,
CSRF and existing cloud/router/streaming/RBAC regressions.

Earlier failing attempts were resolved before the final passing Core run: incorrect
bootstrap-secret test fixture, Mockito replacement of a throwing stub, missing local
Java selection, a disposable-container startup timeout and the excessive initial
permission grants. A temporary worktree dependency junction also prevented Turbopack
building; installing dependencies offline inside the worktree resolved that failure.
These are not outstanding product defects. The unrelated full-lint failure remains
a limitation of the tested snapshot, not a claim about later agents' fixes.

Real files/PDFBox/PostgreSQL were exercised, but embedding and generation in the
end-to-end automated scenario were simulated. Local Ollama model discovery was
read-only; no suitable embedding model was configured and verified. No paid cloud
request, real-model RAG, browser/manual acceptance, physical Voice/hardware test,
ARM64 deployment, PDF fuzzing, scale benchmark or backup/restore drill is claimed.

## Configuration and operation

Required services: existing Core/Web/PostgreSQL, existing K-AI for generation,
and an explicitly configured local Ollama embedding runtime/model. No extra service
or authentication system was added. Follow [the operations guide](../k-data.md).

| Variable | Tested-branch default / purpose |
| --- | --- |
| `KYRION_KNOWLEDGE_ROOT` | `./data/knowledge`; persistent private originals |
| `KYRION_KNOWLEDGE_MAX_BYTES` | `10485760`; upload limit, maximum configurable 50 MB |
| `KYRION_KNOWLEDGE_PARSER_JAR` | `build/libs/knowledge-parser.jar`; standalone parser artifact |
| `KYRION_KNOWLEDGE_EMBEDDING_URL` | `http://127.0.0.1:11434`; trusted operator-owned local HTTP endpoint |
| `KYRION_KNOWLEDGE_EMBEDDING_MODEL` | Empty; must name an installed embedding model |
| `KYRION_KNOWLEDGE_EMBEDDING_DIMENSION` | `768`; must match actual model output |

Build with Java 21 in `services/core` using `gradlew.bat bootJar`. The build also
creates `knowledge-parser.jar`; distribute both jars, not a broad wildcard selecting
the wrong artifact. Existing development starts Core with `gradlew.bat bootRun`
and Web with `pnpm dev` in `apps/web`; AI keeps its existing start procedure.
These commands are instructions for resumption, not actions performed at closeout.

Node/installer Compose mount `/var/lib/kyrion/knowledge`. Bind storage must be
private and writable by service UID/GID 10001; the installer prepares that directory.
The installer does not install AI/models. Container loopback is not host loopback.
An unset model yields an explicit setup failure; fixing setup requires reindexing.
PDF limits are 128 MB heap, 64 MB metaspace, 20 seconds, 200 pages and bounded text;
parsing does not perform OCR or execute/fetch embedded content. It is not an OS sandbox.

Pending jobs survive restarts. Expired leases have bounded recovery attempts;
publication verifies the live revision/lease and deletion state. File cleanup retries;
unreferenced originals/temp uploads older than 24 hours are swept. Reindexing hides
the previous revision until successful publication. Changing model/dimension requires
explicit reindexing. Search is initially capped at 100 documents/space and 600
chunks/document, with at most three chat excerpts and a bounded context budget.

For backup, stop Core and capture the database plus matching file root as one
protected, checksummed backup set. Keep audit/credential keys under existing separate
secret policy. Database-only/personal JSON export does not include originals.
Restore into isolated targets first; do not restore over a live installation.
No secret or credential value is recorded here.

## Cross-agent dependencies and integration order

The branch and shared checkout are **not a jointly validated final state**.
At inspection the same V36 filename had different Git blob IDs:

- Shared `74b2f66`: `3c98280c07139b8a678576b93af1e03f571462e5`.
- Tested `25b6fee`: `634fd19b2b90fb9ba9654775fab7965102a48e8e`.

These are Git blob IDs, not Flyway checksums. Whether either V36 was applied to any
non-test installation is unknown. Do not overwrite an applied migration or run a
blind Flyway repair. The tested version preserves restricted permission grants;
the shared version observed here still contains the earlier broad role defaults.

Other observed shared/feature differences include source checks/persistence in
`AiOrchestration.kt`, job claim/PROCESSING ordering, strict search parsing, embedding
error contracts and RBAC defaults. Shared commit `f2da1d9` adds later personal-context
restrictions for unverified users; it is another agent's work and must be preserved.
Spaces has its own active worktree and canonical ownership decisions.

Integration should proceed in this order: establish migration/application history;
review the completion diff against current Core security/context changes; resolve
shared contracts and ownership with K-AI/Memory/Spaces owners; then validate the
combined branch before any runtime rollout. No merges, migration edits or changes
to other agents' handovers were made for this task.

## Open TODOs

No TODO is completed merely because related code exists. Counts: **10 total:
1 P0, 4 P1, 4 P2, 1 P3**. P0 is an integration/release gate, not an assertion of
an observed production breach.

### KDATA-001 — Resolve V36 history before integration

- **Priority:** P0 — release blocker / database-history risk.
- **Problem:** Two branches contain different SQL under V36; applied runtime history
  is unknown. Blind replacement could fail Flyway validation or change restricted grants.
- **Components:** V36, Flyway history, Core RBAC and release integration.
- **Current state:** Divergence confirmed by blob IDs above; no production inspection performed.
- **Next steps:** Inventory intended target installations and applied Flyway versions/checksums;
  compare both variants; agree a migration-safe reconciliation with repository owners.
  If any version is applied, plan an additive correction without overwriting history.
- **Dependencies:** Other agents' commits and actual deployment/database history.
- **Acceptance:** One documented release migration history; upgrade preserves existing data
  and restricted grants; fresh and representative existing-schema tests pass together.
- **Risks:** Checksum mismatch, inappropriate grants, incompatible upgrade or unsafe repair.

### KDATA-002 — Integrate the tested completion with current security/context work

- **Priority:** P1 — required integration, not yet jointly tested.
- **Problem:** `25b6fee` is isolated; later root commits do not contain all tested hardening.
- **Components:** AI orchestration, context builder, knowledge repository/worker/API,
  security interceptor/RBAC, Web chat/transport and Python contracts.
- **Current state:** Both branches contain knowledge code, but differ at security-sensitive
  boundaries; later verified-user restrictions were not included in this agent's tests.
- **Next steps:** Review `git diff feat/k-data-m01 <current-root-ref>` for affected paths;
  reconcile source rechecks, stream IDs, saved references, job lock ordering, local-only
  policies and error contracts while retaining newer identity/context restrictions.
- **Dependencies:** KDATA-001; K-AI/Memory and stabilization owners.
- **Acceptance:** Combined cross-user/admin, job-race, consent, streaming and source tests
  pass; reference reload works; no newer privacy restriction is lost.
- **Risks:** A textually clean merge could silently remove source persistence, fencing or consent checks.

### KDATA-003 — Perform real embedding and user RAG acceptance

- **Priority:** P1 — essential runtime acceptance missing.
- **Problem:** The automated end-to-end scenario uses simulated models; real retrieval
  quality, dimension/setup and final grounded answers remain unverified.
- **Components:** Local runtime, embedding configuration, Core/K-AI, Knowledge/chat UI.
- **Current state:** Setup-required and adapter failure behavior tested; no suitable local
  embedding model configured/verified; no browser/manual RAG acceptance.
- **Next steps:** Explicitly select/install an embedding-capable local model, verify its
  dimension and container reachability, configure it and use disposable users/documents.
  Exercise upload/status/question/source/download/reload/delete and cross-user denial.
  Check cloud-selection/toggle transitions and embedding-busy/setup messages in the UI.
- **Dependencies:** KDATA-001/002, local model resources and operator configuration.
- **Acceptance:** A real local answer is grounded in the uploaded document with correct
  references; deletion and isolation hold; no cloud fallback or paid request occurs.
- **Risks:** Model/context mismatch, weak retrieval, setup confusion or misleading citations.

### KDATA-004 — Verify database-plus-file backup and restore

- **Priority:** P1 — recoverability unproven.
- **Problem:** Procedure is documented but has not been exercised as a complete backup set.
- **Components:** Original-file volume, PostgreSQL, audit/credential secret handling, operations.
- **Current state:** Existing database backup alone does not cover original files;
  no portable knowledge export or isolated restore drill was implemented.
- **Next steps:** Use disposable content; stop writes, capture matching DB/files/checksums,
  restore into isolated targets, validate ownership/download/search and pending-job recovery.
- **Dependencies:** Stable migration history, KDATA-003 and existing backup owner.
- **Acceptance:** A recorded drill recovers matching originals, metadata, permissions and
  searchable content without touching the active installation or leaking secrets.
- **Risks:** Inconsistent snapshots, missing originals/keys, private unencrypted backup data.

### KDATA-005 — Validate deployment packaging and shared Voice compatibility

- **Priority:** P1 — target-runtime acceptance missing.
- **Problem:** Builds/config validation do not establish a fresh installer or ARM64 runtime;
  shared optional Voice orchestration is not a physically verified Voice-RAG experience.
- **Components:** Core app/parser jars, Docker/node/installer configuration, local runtime,
  shared Voice call site and existing session policy.
- **Current state:** Local JVM/Web builds and Compose/installer tests passed; no deployment,
  hardware test, restart acceptance or satellite knowledge-control UI was added.
- **Next steps:** On an authorized isolated target verify both artifacts, private volume
  permissions, read-only container/temp behavior, local runtime addressing and job restart
  recovery. Coordinate optional knowledge intent through existing Voice policy if required.
- **Dependencies:** KDATA-001/002; installer/stabilization and Velora owners; target hardware.
- **Acceptance:** Target startup/restart preserves originals/jobs, setup failures are explicit,
  ordinary Voice is unchanged and any claimed Voice RAG has documented real evidence.
- **Risks:** Wrong jar, unwritable bind mount, loopback mismatch or accidental Voice regression.

### KDATA-006 — Review hostile PDF/resource behavior beyond fixture coverage

- **Priority:** P2 — hardening and operational evidence.
- **Problem:** Parser separation and limits are tested with selected fixtures, not fuzzed;
  the process is not an OS sandbox and operator-controlled runtime/DNS remains trusted.
- **Components:** PDFBox subprocess, upload/storage, extraction limits and service account.
- **Current state:** Valid/encrypted/scanned/malformed PDF tests pass; limits exist; no
  adversarial corpus, prolonged load test or target-level sandbox assessment was run.
- **Next steps:** Review the chosen parser version and isolated corpus; test timeout,
  decompression/large-output/page limits, cleanup and concurrent upload failure behavior.
- **Dependencies:** Stable packaged parser and security/operations review.
- **Acceptance:** Bounded resource/cleanup behavior is evidenced and operational limits documented;
  any further sandbox requirement is explicit rather than inferred from subprocess isolation.
- **Risks:** Parser vulnerabilities, resource exhaustion or residual sensitive temporary data.

### KDATA-007 — Bind future organization knowledge to canonical Spaces

- **Priority:** P2 — planned extension, outside personal M01.
- **Problem:** Organization ownership is reserved in the domain but deliberately unavailable
  in persistence/API; canonical membership/document authorization is not integrated.
- **Components:** Knowledge spaces, future additive migration, Spaces and tenant authorization.
- **Current state:** Personal-only SQL/HTTP; separate Spaces worktree exists.
- **Next steps:** Review the final canonical schema/contracts with its owner; design additive
  FKs and ownership rules; implement membership-scoped query authorization before UI exposure.
- **Dependencies:** Spaces completion and KDATA-001/002; dedicated isolation tests.
- **Acceptance:** Organization data is accessible only through verified membership/document
  policy, with cross-organization tests and no implicit personal-data admin override.
- **Risks:** Duplicate ownership systems, incompatible migration or tenant-data disclosure.

### KDATA-008 — Measure exact-search scale and plan index evolution

- **Priority:** P2 — documented small-index limitation.
- **Problem:** Exact array search has no pgvector acceleration, lexical fallback or measured
  target-hardware performance; changing model/dimension requires explicit reindexing.
- **Components:** Knowledge chunk persistence/retrieval, embedding model/index configuration.
- **Current state:** Functional bounded exact search, one active model/dimension, conservative
  chunk/context budgets; old revisions hidden during reindex.
- **Next steps:** Benchmark representative private-data-free corpora; measure quality/latency
  and storage; choose whether a deployable pgvector migration or other change is justified.
- **Dependencies:** Real model acceptance, deployment contract and migration decisions.
- **Acceptance:** Documented scale envelope and validated model-change behavior; any index
  change preserves authorization-before-retrieval and atomic publication.
- **Risks:** Latency/resource growth, weak relevance or mixed/incompatible vectors.

### KDATA-009 — Establish a combined verification baseline and resolve inherited lint

- **Priority:** P2 — verification debt owned across workstreams.
- **Problem:** Recorded results describe the isolated snapshot, not later root/Spaces changes;
  full Web lint failed on a pre-existing personal-memory purity issue at that snapshot.
- **Components:** Web memory panel, CI/test environment, shared Core/AI/Web regression baseline.
- **Current state:** Milestone files pass lint and builds; later memory commits may have
  changed the failing line, but no new full-lint result was claimed at closeout.
- **Next steps:** Coordinate ownership of the memory fix, inspect current code and run the
  appropriate combined checks after integration; retain disposable-container isolation.
- **Dependencies:** KDATA-002 and Memory/stabilization owners; reliable Java/Docker setup.
- **Acceptance:** Combined-branch test/build/lint evidence is recorded without attributing
  isolated historical counts to a different checkout or masking failures.
- **Risks:** False green release claims, recurrence of environment timeouts or shared-file overwrites.

### KDATA-010 — Decide provenance retention for stopped partial answers

- **Priority:** P3 — optional consistency improvement.
- **Problem:** Sources display during streaming but only completed answers persist references;
  reloading a stopped partial answer can lose its source list.
- **Components:** AI stream lifecycle, saved answer-source repository and conversation UI.
- **Current state:** Completed-answer references persist correctly; stopped-partial behavior
  is explicitly documented. Generated answer text survives source deletion under existing
  conversation retention; source deletion does not erase that historical answer.
- **Next steps:** Agree expected retention/cancellation UX, then design minimal source
  persistence/removal consistent with existing conversation lifecycle and deletion policy.
- **Dependencies:** K-AI/conversation owner and KDATA-002.
- **Acceptance:** Any supported stopped-answer references survive reload with correct message
  association, no foreign/deleted source exposure, and explicit retention semantics.
- **Risks:** Orphan references, misleading provenance or unexpected private-data retention.

## Current State

1. **Demonstrably works at `25b6fee`:** automated personal upload/storage/parsing,
   PostgreSQL ingestion/retrieval/isolation, job fencing/deletion, simulated K-AI
   streaming/source persistence, bilingual contracts/UI build, and recorded regressions.
2. **Implemented but not fully validated:** real local-model RAG, browser UX, target
   installation/restart, physical Voice compatibility and database-plus-file recovery.
3. **Currently unavailable/failed in that snapshot:** RAG needs explicit embedding setup;
   organization knowledge/OCR/cloud document context are unavailable by design; stopped
   partial answers do not save references; full Web lint has the inherited failure.
4. **Main risks:** divergent V36 history and unintegrated security changes, followed by
   unverified recoverability/runtime/model behavior. No active production leak or loss
   was established by this session.
5. **First resumption check:** identify the intended branch and actual applied migration
   history before any merge, schema change or claim that the tested snapshot is deployed.

## Recommended Next Steps

1. Resolve KDATA-001 migration history and integrate KDATA-002 without losing newer privacy rules.
2. Configure a local embedding model and execute KDATA-003 real-user RAG acceptance.
3. Complete KDATA-004 backup/restore and KDATA-005 isolated target-runtime acceptance.
4. Record a combined test/build/lint baseline with the other workstreams (KDATA-009).
5. Plan organization authorization, parser hardening and scale work only after those gates.

This closeout creates only this agent's documentation. No new feature/refactoring,
migration modification, paid provider request, service restart or production deployment
was performed. A documentation-only commit is recorded in the final response; the tested
implementation commit remains `25b6fee` regardless of subsequent documentation commits.
