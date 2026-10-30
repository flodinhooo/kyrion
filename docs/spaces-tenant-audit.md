# Spaces Milestone 02 tenant-boundary audit

Combined-source update: personal K-Data is now integrated. Its real protected
`/v1/knowledge/spaces` endpoint replaces the branch's absent-API assumption.
Knowledge retains per-account ownership, uses current Spaces-aware RBAC, and
ingestion rechecks permission before extraction, embeddings and publication.
Claim/publication fencing also rejects suspended canonical Spaces. New disposable
PostgreSQL tests cover foreign-Space metadata/content/delete/reindex/search denial,
suspension before embedding and suspension during embedding. Organization sources
and multi-Space runtime remain unavailable. The original branch audit below is
historical evidence, not a claim of exhaustive combined worker certification.

This is a bounded audit of Agent 3's branch, not certification of multi-tenant
hosting. `SingleSpaceRuntimeGuard` remains. Core has no public multi-Space
provisioning or switching API. Tests seed a second independent Space and system
roles deliberately; this does not enable that topology for real installations.

## Central authority

`TenantBoundary.actor(userId)` resolves active membership from the database and
checks active Space plus strict identity policy. `shared(userId, spaceId)` rejects
foreign Space context; `personal(userId, ownerId)` rejects another account even
within the same Space. `workspace(spaceId)` validates shared worker scope.
`RbacService.require` and `lockIdentity` use this authority. Permission queries now
join assigned roles to the account's own Space; no permission cache is introduced.
Existing immutable membership and cross-Space role triggers remain in force.

Browser `spaceId`, `actorId`, headers, tool arguments and guessed UUIDs are not
authentication context. Interceptors derive request attributes from a session.
Public setup still requires the existing secret, bootstrap marker and serialized
transaction. Public registration requires an invitation, plus mailbox proof when
policy requires it. Unknown identity routes are not proxyable.

## Reviewed paths and evidence

| Subsystem | Reviewed/enforced boundary | Evidence and limits |
| --- | --- | --- |
| Authentication/RBAC | Active account/Space, verified strict identity, role-to-account Space join, immutable membership | Existing bootstrap/Owner/delegation tests plus identity and two-Space tests; no universal Owner |
| Rooms and nested devices | Existing owner predicates; new deferred room/connection composite FK | Foreign reads/writes and forged nested room association rejected in PostgreSQL |
| Nanoleaf/credentials/device actions | Catalog and connection lookup receive trusted owner; Action Orchestrator rejects mismatched human actor and Space before handlers | Existing IDOR/zero-gateway-call tests; credential ciphertext/nonce/key preserved; no physical verification |
| Gateway/Zigbee | Node credential resolves owner; heartbeat validates active workspace; async button job revalidates node workspace; node/command composite ownership FK | Existing gateway/command tests and explicit workspace guard; full concurrent hardware/event/retry acceptance remains incomplete |
| Home Assistant | Scoped connection/import repositories; composite imported-device owner FK; refresh validates active workspace before importer | Actual executor test proves suspended Space causes zero importer calls; HA provider payload/physical acceptance remains separate |
| Spotify | Pending OAuth state binds owner; callback checks owner; token repository, devices/playback/control use trusted shared workspace | Source reviewed and existing adapter tests; no live OAuth acceptance or exhaustive two-Space playback-race test |
| Local calendar | Shared workspace resolved through RBAC; repository ID/owner predicates; versioned writes | Existing foreign-ID CRUD and permission tests retained |
| Google Calendar/OAuth | Personal actor-owned connection; sync mapping includes actor; scheduling state is per actor; sync rechecks permissions between events | Existing account separation and scheduling tests retained; provider writes cannot be rolled back by local transactions |
| Preferences/model policy/budgets | Preferences/usage keyed by actor, policy keyed by resolved workspace | New two-Space policy/usage and manipulated-parameter tests; limits retain existing per-actor accounting semantics, not pooled tenant billing |
| Conversations/memories | Personal owner predicates retained; Core reconstructs local memory/history and cloud current-message context | Existing direct-ID read/write, backup/retention and cloud-consent tests retained; foreign conversation prepare fails before provider |
| K-AI streaming/fallback | Explicit captured actor/session, authority and current routing policy rechecked before provider and on received events; uninvoked reservations released without charge | New async revoked-session and prepared-policy-change tests prove zero provider calls; no cloud consent/provider escalation added |
| Native tool execution | Browser/model input supplies proposals, never trusted owner context; execution uses scoped catalog and handlers | Existing proposal validation/action tests; native tool events remain rejected on generative stream |
| Legacy proposal generation | Bypasses K-AI route/budget authority | Disabled for BUSINESS and any HOME Space with an explicit AI policy; direct manual device controls remain available |
| Voice/satellite/STT/TTS | Satellite credential and session ownership revalidated; pending actions keyed by Space/session/satellite/turn; playback ack keyed by session/turn | New foreign-action/session/ack tests; BUSINESS satellite and Web synthesis disabled pending principal/routing integration; HOME behavior retained |
| Web synthesis | Existing direct AI-service path | Now requires session, CSRF, HOME context and conversation permission; Business denied with zero AI-service calls |
| Background jobs/leases | Calendar actor passed explicitly; HA owner read from DB; queued Zigbee node carries owner and revalidates | No ambient thread-local identity required for these jobs; worker shutdown/cancellation and multi-process guarantees remain incomplete |
| Audit | Existing owner-scoped sealed chains; explicit actor/owner/correlation passed to important operations | Existing integrity/rollback tests retained; recovery commits denial events without codes and rolls back on audit failure |
| Fixed response/cache data | Device state cache uses `(owner, device)`; dynamic voice template scope hashes owner; fixed public templates contain no private tenant context | Source review; streaming/cache teardown across multiple real installations is not certified |

## Explicitly guarded or absent areas

Business satellites currently act as the root owner instead of an identified
person. They cannot be used safely as individual Business identities. The
`BUSINESS_VOICE_IDENTITY_REQUIRED` guard rejects authenticated Business satellite
use and Web synthesis. The browser voice entry point/preview are also disabled
for Business, because browser recognition/synthesis can use vendor cloud services
outside Core. This is a product capability constraint, not a claim to control an
authorized user manually copying text into another browser/OS service. This blocks STT, TTS, chat/tool context and action execution
through those paths; it does not invent per-person attribution. HOME continues
using its existing explicit satellite enrollment model. Device-proposal generation
has a separate guard until it uses K-AI routing, consent and budget authority.

Discovery, global provider/model catalog, scheduler serialization and the AI-service
trust network are still installation-level. Run AI/gateway/provider HTTP surfaces
on their intended private network; this change does not add service-to-service
tenant credentials or authorize public AI-service exposure. No WebSocket resource
channel exists in this branch; voice and model streams are HTTP NDJSON/PCM paths.
Gateway long polling/retry isolation, every provider action, long-running stream
cancellation, and all cache lifecycles are not exhaustively certified.

## Parallel knowledge and context integration dependency

The original worktree contains a concurrently changing personal-context/knowledge
implementation absent from this branch: `context/ContextBuilder.kt`,
`context/KnowledgeContextAssembler.kt`, `knowledge/api/KnowledgeController.kt`,
`knowledge/application/KnowledgeService.kt`, `knowledge/persistence/KnowledgeRepository.kt`,
and document storage/embedding/retrieval workers. No code was copied or merged.
The knowledge API is absent here and is explicitly tested as 404. No document,
embedding, RAG or vector-isolation claim follows from that absence.

Before integrating those features, their entry points must invoke
`TenantBoundary.actor(actor)` and enforce resource-account ownership with
`TenantBoundary.personal(actor, resourceOwner)` (or an explicitly reviewed shared
Space contract). Queries, document blobs, chunks, embeddings, source provenance,
search indexes, deletion jobs and task results must carry the same immutable scope.
Add the protected knowledge route family to the shared interceptor and preserve
the other branch's knowledge permission grants. Tests must independently seed
two Spaces and verify document upload/list/download/delete, guessed document and
chunk IDs, lexical/vector retrieval, AI prompt source inclusion, embedding jobs,
cross-account same-Space separation, async retries and streamed citation metadata.
Those exact tests cannot run against absent, concurrently modified code.

Also reconcile parallel edits to `ConversationController`, memory repositories,
K-AI orchestration, Web shell/chat/context controls and Core build configuration.
Agent 3's V37 already collides with the parallel calendar-context V37. Preserve
applied history and resolve that explicitly before integration; V38 adds this
milestone's tables without changing V37. Run combined migration preservation and
security tests after resolving the collision. Do not remove the startup guard
until every table/blob/index/worker/provider/stream boundary is tested together.

## Managed hosting and support

Future managed hosting additionally needs service credentials/tenant routing,
per-tenant encryption/secret boundaries, worker principal grants, queue isolation,
policy-aware retrieval, tenant-specific quotas, restore/rollback isolation and
continuous authorization on long-lived operations. They are not implied by this
local MVP. SUPPORT_OPERATOR remains a design-only, separate identity with
customer-approved, scoped, expiring, revocable, audited grants and MFA. It has no
permanent customer membership, global OWNER, implicit memory/document access,
remote tunnel or credential bypass.
