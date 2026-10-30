# Personal Context Engine — K-AI Milestone 03

## Implemented ownership and request path

Core's `ContextBuilder` extends the existing conversation repository, extractive
summary cache, personal-memory selector and account AI preferences. It does not
maintain another history, memory database or vector store. Both the existing
turn API and the Core generation path use this builder; Velora already uses that
same generation path. Wake word, STT, TTS and playback were not changed.

Satellite credentials identify an enrolled device, not the speaker. Consequently
satellite dialogue explicitly disables all personal context and uses only the
current utterance. It does not inherit the owner's history, memory, calendar,
preferences or document context. Authenticated browser Voice requests can use
personal context for their logged-in account. A verified-speaker path may opt in
server-side in future; the Voice service defaults to no personal context. There
is no browser/body switch for overriding satellite identity verification.

The builder reloads the conversation for the authenticated account and truncates
it at the requested user turn. A workspace owner is never substituted for the
personal account. Missing identity fails closed with `UNAUTHENTICATED`; a missing
or foreign conversation cannot be retrieved. `conversations:read` is required,
and personal-memory retrieval additionally requires `personal_memories:read`.

There was no platform Space/Tenant implementation in the main checkout at the
start of this milestone. The independent Spaces worktree was left untouched.
Parallel Knowledge work has since introduced its own collections and assembler;
that is a separate workstream, not proof of platform tenant isolation. This
builder does not retrieve those documents or shared business data. Future
enterprise retrieval needs the authoritative Space identity and access contract.

## Deterministic selection and budgets

The current conversation has priority. Optional context uses at most one third
of the input budget and never displaces the current message. Optional selection
order is confirmed relevant memories, explicit routing preferences, explicitly
enabled personal calendar data, then lexical matches from previous conversations.
Tie breaking uses relevance, modification time and stable identifiers.

- Memories: existing 100-candidate, three-selected limit; sensitive records need
  stronger lexical overlap. Proposed, superseded, inactive, expired and excluded
  categories are not used.
- Previous conversations: disabled by default; search at most 20 owned recent
  conversations and their last 20 messages; select at most two relevant user
  statements, bounded to 600 characters each. No model or network search occurs.
- Preferences: disabled by default; only typed local-only/routing preference
  metadata is included, without credentials.
- Personal calendar: disabled by default; requires `calendar:read`, a calendar
  query, and exact account ownership. At most two upcoming events within seven
  days are retrieved. There is no workspace or enterprise calendar substitution.
- Documents/business data: blocked on this builder until explicitly integrated.

Existing deterministic compaction and persisted summaries remain in use. Context
is checked against the configured input budget; generation also subtracts the
configured maximum output and system allowance from known model context limits.
Unknown limits use the bounded existing default. Token counts are deterministic
character estimates, not exact vendor tokenizer guarantees. Provider validation
and the existing request/budget ledger still apply. Small budgets omit optional
items instead of overflowing. Oversized current messages fail visibly.

Additional source adapters implement `PersonalContextDataSource`, receive a typed
personal scope and declare a permission checked before retrieval. Their results
are subject to the same budget. An adapter still must enforce its authoritative
scope in storage; this interface is not permission to access enterprise data.

## Privacy and observability

Source descriptors identify kind, record ID, privacy class, selected state,
reason and estimated tokens without copying source contents into audit logs.
Local context assembly records a minimal correlated audit event. The preview API
re-evaluates current settings and data; it is not a frozen reconstruction of an
earlier generation. Routing and generation may therefore show different previews
if data or settings changed between calls.

Cloud has a separate early-return path: only the current message is emitted.
History, memories, preferences, calendar and documents are classified as blocked
for cloud. Existing server enablement, exact provider consent and same-boundary
fallback rules remain in force. There is no additional-context cloud opt-in in
this milestone. A future disclosure expansion requires a versioned server policy
and renewed category-specific consent; browser flags cannot enable it.

Quoted retrieved statements are data, not execution authority. Models still
cannot execute devices; Core validates and audits actions separately.

## Memory/API/UI changes

Existing memory categories, provenance, ownership, timestamps, confirmation,
conflict resolution, editing and deletion remain intact. Additive migrations V35
and V37 extend the existing tables with active/expiry metadata and context opt-ins.
No records are rewritten or deleted by these migrations. V36 belongs to the
parallel Knowledge workstream.

New authenticated operations under the existing memory permission mapping:

| Endpoint                                           | Behavior                                                                          |
|----------------------------------------------------|-----------------------------------------------------------------------------------|
| PUT `/v1/memory/context-settings`                  | `historyEnabled`, `preferencesEnabled`, `kyrionDataEnabled`, allowed `categories` |
| PATCH `/v1/memory/{id}/validity`                   | `active` and nullable ISO-8601 `expiresAt`                                        |
| POST `/v1/memory/{id}/reject`                      | Remove an owned proposed memory, with rejection audit                             |
| GET `/v1/memory/context?conversationId=…&turnId=…` | Recomputed source descriptors for an owned turn                                   |

List/propose/confirm/update/delete APIs are retained. All memories still need
confirmation, including sensitive statements. No automatic extraction or hidden
confirmation was added. Rejection physically deletes the proposal, matching the
existing local deletion policy. Expiry excludes records at retrieval time; it
does not delete stored information. Users can inspect, correct, deactivate or
delete expired records. Validity does not silently reactivate superseded records.

The existing profile Memory panel now exposes provenance IDs and timestamps,
active/expiry controls (UTC), category selection, source opt-ins and a source
inspector for memories linked to conversation turns. Text remains German/English.
Same-origin API routes preserve session, CSRF and Core ownership/RBAC enforcement.

## Validation and remaining limits

Core integration coverage includes expiry, deactivation, category filtering,
cloud exclusion, bounded history, personal-account isolation, unknown identity,
validity/rejection APIs and the shared Voice context path. Web coverage validates
source/validity contracts and authentication/CSRF/ownership error forwarding.
Existing Core, AI and Web regression suites and builds were run; exact outcomes
and concurrent-workstream failures are recorded in the delivery report.

No production deployment, live database migration, destructive user-data action
or paid cloud request was performed. Physical Velora acceptance, exact model
tokenizers, immutable per-generation source snapshots, deeper retrieval quality
evaluation and integration with authoritative platform Spaces remain follow-up.

## Delivery verification (2026-10-30)

- Targeted Core regression run: 18 tests passed, including PostgreSQL-backed
  memory/context/Voice checks, cloud policy, router and transport contracts;
  `bootJar` passed using isolated output under `.run/kai03/core-build`.
- AI: 166 tests passed, Ruff lint and compilation passed. This count includes
  concurrent Knowledge tests; no paid/live cloud acceptance was used.
- Web: 159 tests and TypeScript passed; production build passed. Lint restricted
  to changed Memory/Context components, contracts and routes passed.
- Full Core runs were attempted. One isolated run completed 239 tests with one
  failure in the existing V30-upgrade preservation test: parallel V36 grants
  additional Knowledge permissions to existing roles. A later full run had a
  PostgreSQL testcontainer startup timeout and two new Knowledge integration
  failures. These external changes were preserved rather than changing their
  permission policy or weakening the regression assertion.
- Full Web lint still reports a React `set-state-in-effect` error in the parallel
  `knowledge-view.tsx`. The Memory/Context files have no lint errors.

The entire concurrently changing repository is therefore not claimed fully
validated. Resolve the parallel Knowledge migration/test/lint issues and rerun
all suites on a coordinated revision before rollout. This work made no live
migration or deployment. Source snapshots and physical satellite acceptance
remain follow-up work.
