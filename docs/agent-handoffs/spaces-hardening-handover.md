# Spaces hardening continuation

Date: 2026-10-31. Source implementation and isolated verification only. No
deployment, live migration, merge, provider-account operation or hardware rollout.
Multi-Space runtime remains **blocked**. This is a continuation of the combined
source, not reapplication of the original Spaces feature branch.

## Actual starting point

- Started from `master` at `bdd6f83`; work proceeds on `fix/spaces-hardening` in
  `E:/dev/Kyrion/kyrion`. No old worktree was checked out or copied.
- Existing worktrees: Spaces `024e1e6`, K-Data `25b6fee`, recovery `547f0ae`,
  V39 compatibility `f07c20a`. The recovery worktree was already dirty (visible
  as ` m .worktrees/calendar-ha-recovery`); it is preserved and never staged here.
- Combined source already includes Spaces M01/M02, real SMTP mailbox challenges,
  DNS TXT proof and local recovery; personal K-Data, K-AI routing/context/durable
  accounting, Calendar/HA recovery and recent Velora no-speech behavior.
- Historical feature handoffs describe V37/V38 and an absent Knowledge API.
  Those statements are superseded by combined V38/V39 and the real K-Data API.
- Read-only SQL against `kyrion-postgres` found successful V1–V39, including
  V31 checksum `1755433543`, V36 `personal_knowledge` (`-775801516`), V37
  `personal_calendar_context_opt_in` (`-1093609037`), V38 `kyrion_spaces`
  (`1162782822`) and V39 identity/recovery (`1560355568`). V40 is source-only
  in that database. No repair, renumbering or checksum mutation was performed.

## Implemented changes

1. Domain verification now persists failed checks and audits them as FAILED,
   without addresses, TXT credentials or domain plaintext in the failure event.
   The API distinguishes PENDING, VERIFIED and FAILED. Expired/invalidated proof
   with no current evidence is FAILED; rotation resets the pending failure.
   A failed recheck/replay does not erase independently unexpired proof.
2. Expected DNS verification denials commit their failure metadata and sealed
   audit together. Unexpected SQL/audit errors roll back both. This transaction
   exception is limited to `verifyDomain`, not policy/enrollment/email mutation.
3. Human device actions recheck active membership, Space and `devices:execute`
   before the idempotency lookup, handler invocation and each target dispatch.
   No second adapter call follows permission revocation between batch targets.
4. AI dispatch and received events recheck conversation read/create permission,
   selected-memory read permission, current routing policy and source validity.
   Error paths discard buffered provider/source metadata; previously they could
   emit citations after the backing document had been deleted.
5. Knowledge search rechecks current actor authority after blocking query
   embedding and before retrieval. Voice rechecks the authenticated satellite
   session after blocking transcription and before releasing its transcript.
6. Gateway/Voice enrollment and direct satellite bootstrap reject inactive
   workspaces. Enrollment consumption rolls back if the canonical Space is
   suspended before redemption.
7. Existing Identity Web settings show persisted failure, empty/loading states,
   expiry dates, exact-subdomain instructions, per-domain retry/rotation and
   refreshed status after failed mutations. Strict activation is unavailable
   without SMTP/recovery. German and English texts are supplied together.
8. Strict domain changes read recovery prerequisites under the existing valid
   policy. Excluding a verified OWNER now reaches the explicit
   `POLICY_MEMBER_LOCKOUT` check and rolls back, instead of reauthorizing the
   OWNER against the staged excluding allowlist and returning a generic denial.

## Business policy decisions retained

Existing ADR 0032 remains authoritative; no replacement verification subsystem
or new mail-provider dependency was introduced. DNS uses a random Space-bound
TXT value, hashed at rest, a 30-minute challenge, 30-day evidence and bounded
resolution. Challenges/checks retain the existing process-local per-actor rate
limit. The host resolver is trusted; application DNSSEC/continuous domain
ownership monitoring is not implemented. No arbitrary URL fetch is used.

IDNA/STD3 normalization and exact domain matching remain. Every subdomain needs
its own proof. SMTP mailbox proof is distinct from DNS and local attestation;
historical addresses are never silently verified. Strict policy requires SMTP,
verified allowed addresses for every enabled member, local recovery and explicit
invitation revocation. Issuance and acceptance check current policy. Changes to
strict allowlists revoke outstanding invitations; proof cannot resurrect one.
Failed lockout-inducing changes roll back. Existing members/OWNER retain access
after DNS expiry; disabling policy remains possible. HOME requires no domain.
Real customer SMTP delivery and external DNS ownership were not contacted here.

## Compact boundary matrix

Evidence names refer to tests in `services/core/src/test/kotlin/dev/kyrion/core/`.
HTTP tests use MockMvc with real services/PostgreSQL; external adapters are
simulated. Source inspection alone is explicitly not an isolation certificate.

| Path | Trusted context origin | Existing/current enforcement | Remaining gap or limit | Test evidence |
| --- | --- | --- | --- | --- |
| HTTP/auth/session | Server session → account → immutable Space | Interceptor allowlist, current TenantBoundary/RBAC; unknown routes denied | No client `spaceId` establishes authority | AuthenticationPersistence: Space endpoints; manipulated AI policy parameters; disabled sessions |
| Roles/members/invitations | Locked actor membership and invitation DB row | Scoped role joins/FKs, workspace/row locks, current inviter/delegation checks | Process-local throttles; no public multi-Space provisioning | AuthenticationPersistence: foreign role assignment, expired/revoked/concurrent redemption, role-change escalation |
| Business/mail/domain | Locked BUSINESS OWNER; invitation/Space/mail-bound proof | SMTP and DNS proofs separate; exact domain; current policy checked on acceptance | SMTP/DNS production acceptance remains operator work | AuthenticationPersistence: strict policy, changed policy/revoked invitation, subdomain denial, DNS rotation/expiry/failure/audit rollback |
| Rooms/devices/credentials | Session-derived resource owner | Owner predicates, composite room FK, scoped catalog; action authority rechecked per target | Direct provider endpoints are request-authorized; complete in-flight provider races not certified | AuthenticationPersistence: foreign Nanoleaf IDs, zero provider calls; nested room FK; revoked batch action |
| Actions/idempotency/native tools | Explicit server ActionContext | Actor/Space permission before cache/handler/target; typed bounded proposals | Gateway command queue does not persist originating human principal; see P0 below | AuthenticationPersistence: revoked human handler and batch; ActionEndpoint/ActionOrchestrator suites |
| HA refresh/import | Owner loaded from DB in scheduler | Explicit workspace check, connection/import owner predicates and composite FK | Provider calls cannot be recalled after dispatch; concurrent multi-process lifecycle incomplete | AuthenticationPersistence: suspended executor makes zero importer calls; HA reconciliation regressions |
| Local Calendar/Google sync | Shared Space through RBAC; personal Google actor | Resource predicates; explicit actor in scheduled lease/batch and recurring permission checks | Global serialization, remote side-effect reconciliation and full cross-Space race coverage remain | AuthenticationPersistence: foreign CRUD, Google account separation, scheduling and mid-batch permission revocation |
| Spotify/YouTube/integrations | Server shared workspace; OAuth state binds owner | Scoped connections/tokens/playback and Core link validation | Exhaustive OAuth/playback/cache race coverage absent | Existing SpotifyIntegrationService and provider-contract tests; source inspection |
| K-Data metadata/blobs/chunks/index/search | Authenticated personal actor, not canonical Space ID from client | Actor-owned knowledge space; owner SQL; scoped storage key; post-embedding reauthorization | Personal only; organization knowledge is not implemented | KnowledgeSecurity: independent canonical Spaces, foreign metadata/content/delete/reindex/search; query-embedding suspension |
| K-Data ingestion/deletion | Job owner resolved from document/knowledge-space DB relation; fenced lease/revision | Recheck create permission before extraction/batches/publication; canonical active-Space fencing | Storage sweeper/deletion lifecycle is installation-managed; full multiple-process/cache lifecycle not certified | KnowledgeSecurity: claim races, retries, expired leases, deletion/suspension during embeddings |
| AI conversations/history/memory/context | Captured actor, personal repository predicates | Current conversation read/create; selected-memory read checks; scoped context; no unknown-speaker personal retrieval | Prepared optional-context preference/content invalidation is not exhaustively certified across all races | AuthenticationPersistence: foreign IDs, personal history/calendar and context tests, stale session/prepared policy tests |
| AI generation/retrieval/fallback/NDJSON | Prepared server actor plus revalidated session callback | Current model policy per event; scoped sources rechecked; failure buffer discarded; no native tool execution | Cancellation while a provider is silent is not a bounded-time guarantee; already dispatched data cannot be recalled | KnowledgeSecurity: delete before/during stream; AuthenticationPersistence: midstream policy withdrawal; AI accounting/fallback suites |
| Gateway polls/commands/results | Node ID + hashed credential → DB owner | Authenticate on polling/completion, active workspace, node/command ownership FK | Queued human permission revocation, credential rotation/retry hardware races remain P0 | GatewayService/GatewayCommand suites and suspended enrollment integration test; no complete long-poll certificate |
| Zigbee queued button jobs | Authenticated node captured with owner | Worker workspace recheck, owner catalog, typed ActionContext | Captured binding/config revocation and complete executor/retry lifecycle not certified | Existing automation/action tests; source inspection |
| Voice/Velora ingress/STT/TTS/PCM | Satellite credential and DB session; separate from human speaker | HOME-only operational guard; per-session/turn pending actions and acks; validation after STT and during existing stream boundaries | BUSINESS voice unavailable until person-level principals; full hardware/cache/cancellation matrix incomplete | VoiceTenantState; VoiceNoSpeech real loopback STT + mocked identity; PCM suites; Business voice/foreign-session integration tests |
| Device/template caches | `(owner,device)` state key; owner-hashed template scope | Existing explicit cache partition; fixed public responses have no private context | Eviction/teardown/restart across multiple Spaces not certified | Existing template/cache tests and source inspection; no new physical cache acceptance |
| Audit/backup/retention | Explicit actor/owner/correlation; personal ownership | Sealed scoped chains, owner backup predicates and confirmed cleanup | Backup restoration can restore spent proof material; rotate credentials after restore | Existing integrity/rollback/backup/retention tests; new failed-DNS audit rollback |
| Resource WebSocket/SSE/external queues | — | No separate Core resource WebSocket/SSE or external queue subsystem found; Core streams use HTTP NDJSON/PCM. AI provider adapters normalize upstream SSE | No new subsystem added; upstream provider adapters are not a resource-channel identity authority | Source inventory; Python provider transport tests were not rerun in this Core/Web-only change |

## Migration compatibility

New additive **V41 `business_domain_verification_outcome`** adds one nullable
`verification_failed_at` column. It changes no existing migration, identity,
membership, credential, DNS challenge hash or historical audit row. Existing
unexpired proof remains VERIFIED. Old source ignores the additional column, but
this is not permission to downgrade Flyway history or bypass validation.

`CombinedMigrationIntegrationTest` exercises actual PostgreSQL fresh/upgrade
histories, synthetic installation-shaped preservation, incompatible feature
history validation failure, and a new V40→V41 domain/SMTP/membership preservation
test. Its separate V40 dump/restore rehearsal stays explicitly pinned to V40;
that historical test must not accidentally assert that latest is still V40.
Already applied feature-specific V36/V37/V38 histories must stop for a reviewed
compatibility plan; no automatic repair is offered.

## Verification and source delivery

- Core: JDK 21 from the existing ignored `.run/stabilization/toolchain/`;
  `services/core/gradlew.bat test bootJar --console=plain`: **326 tests**, zero
  failures/errors/skips; bootJar successful. PostgreSQL Testcontainers execute
  real Flyway, SQL constraints, transactions and service/MockMvc API tests.
  Provider, SMTP, DNS and embedding transports are simulated; Voice revocation
  uses real loopback HTTP transcription with mocked satellite/session authority.
- Web: `pnpm test`: **200 tests / 60 files**; `pnpm lint`, `pnpm exec tsc
  --noEmit`, and `KYRION_BUILD_DIRECTORY=.next-spaces-hardening-build pnpm build`
  succeeded. The build used separate output and did not replace the dev server.
  Next's automatically appended build-directory tsconfig entries were removed
  afterward; they are generated verification metadata, not product configuration.
- `git diff --check` passed. No configured Core formatter/linter task exists;
  Kotlin compilation and the complete test/build pipeline ran. The JVM class
  sharing and Gradle deprecation notices remain non-failing toolchain warnings.
- Failed intermediate tests were not counted as acceptance: an incorrectly
  placed DNS assertion was fixed; the new midstream source-deletion regression
  exposed the buffered-citation leak and passed after fixing the error path.
  The stronger verified-domain replacement test also exposed the staged-policy
  reauthorization error described above; it was corrected before acceptance.
- No browser interaction/visual acceptance, actual mailbox delivery, external DNS
  customer challenge, cloud request, device action or physical voice test was run.
  No running Core/AI/Gateway/Satellite process was replaced or restarted.

Logs are ignored local artifacts under `.run/spaces-hardening-*`. The live
database was read only; migrations ran exclusively in disposable test databases.
Final commit IDs are recorded below; the unrelated dirty recovery worktree is
preserved.

- `bba25e5`: bilingual Identity UI, DNS outcome contract and contract test.
- `e56619b`: Core authority/stream/enrollment hardening, V41 and regression tests.
- The documentation commit is discoverable with
  `git log -1 -- docs/agent-handoffs/spaces-hardening-handover.md`.
- Final own changes are committed. The remaining root status entry is the
  pre-existing modified recovery worktree; no content there is included.

## Release decision and next three steps

`SingleSpaceRuntimeGuard` is retained. Two-Space fixtures deliberately probe
boundaries; they do not authorize concurrent real installations or switchers.

1. **P0:** Carry originating human actor and required capability through Gateway
   queue/claim/retry, revalidate at dispatch, and define explicit integration
   grants for automation. Existing rows must not acquire inferred OWNER authority.
   Include deleted/reconfigured button binding and revoked membership tests.
2. **P0:** Complete combined long-running stream/optional-context/cache/worker
   lifecycle certification: silent-provider cancellation, context opt-out/content
   changes, credentials/session revocation, independent concurrent Spaces and
   multiple-process retries. Existing per-event checks are a bounded improvement.
3. **P1:** Rehearse deployment compatibility and Business SMTP/DNS/operator
   recovery in isolation, then complete provider/physical Gateway/Voice tests.
   BUSINESS person-level speaker identity remains required before voice enablement.
   Only after P0 evidence is complete should an ADR consider removing the guard.
