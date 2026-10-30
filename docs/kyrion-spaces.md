# Kyrion Spaces

Integration note: the combined main checkout includes Spaces and personal K-Data.
Canonical migration numbers are V38 (Spaces) and V39 (Business identity), following
the existing calendar-context V37. Historical branch numbering below is superseded
by [ADR 0033](adr/0033-combined-development-migration-history.md). Multi-Space
runtime remains guarded; organization Knowledge is not enabled.

## Implemented boundary

One local installation has one active HOME or BUSINESS Space. Each account has
exactly one generated `space_id`; membership cannot be moved through an account
update. Home and company accounts remain distinct identities. There is no Space
switcher, public login, cloud dependency, cross-Space membership or provisioning
API. The UUID is the stable Space identifier; no mutable slug is needed.

`/v1/space` derives the current Space from the authenticated account. OWNER can
change its name, product type and default role. Custom additive roles continue to
work. Default role cannot be OWNER. Existing user/role management under `/v1/rbac`
is reused, including deactivation, session revocation and last-owner protections.
The Web entry point is Settings → Kyrion Space; member management links to Users.

Fresh setup collects HOME/BUSINESS and a name using the existing local setup-secret
flow. The durable bootstrap lock, owner, system roles, Space settings and audit
write share the setup transaction. Legacy API callers default to HOME/Kyrion.
Existing installations remain initialized and are not asked to set up again.

## Migration and preservation

V37 is additive. Back up PostgreSQL and the existing credential/audit key files
using the existing backup procedure before applying it. Test the migration against
an isolated restored copy first. No production database was migrated by this work.

For an existing installation, the root workspace owner ID becomes the Space ID.
No device, room, calendar, integration, credential, automation, conversation,
memory, session or historical audit row is rewritten. Existing role grants and
permission sets remain unchanged. Existing invitation hashes and expiry remain;
redeemed invitations receive a consumed-use count. The default Space is HOME,
never inferred from account information. No encryption keys are rotated.

Migration aborts on multiple or missing enabled root owners, nested workspace
ownership, or role assignments spanning workspaces. The exception includes an
actionable `SPACES_MIGRATION_*` diagnostic. Reconcile ownership explicitly on a
restored copy with a local operator; do not choose the earliest email/account or
merge unrelated resource partitions. Apply no manual change to ciphertext or
audit chains. Keep the backup until migration and authorization checks pass.

## Invitations

`GET/POST /v1/space/invitations` lists metadata or issues an invitation;
`DELETE /v1/space/invitations/{id}` revokes it. The compatibility endpoint
`POST /v1/auth/invitations` issues the current default role. Acceptance uses the
existing password-protected account creation at `POST /v1/auth/register`.

Codes contain 256 cryptographically random bits and only SHA-256 hashes persist.
The issuing response is the only opportunity to copy a code. Default lifetime is
24 hours and one use; bounds are 1–168 hours and 1–20 uses. The local Web builds
`/signup#invitation=...` URLs, keeping credentials out of HTTP URLs and referrers.
Acceptance removes the fragment from browser history and requires explicit account
creation. URLs work only where that instance is reachable. Share them privately.

Issuance serializes with RBAC mutations. Creators cannot invite OWNER or grant
permissions they lack. Redemption takes the workspace advisory lock and invitation
row lock, verifies the active Space, expiry, revocation, remaining uses, inviter
status and current delegation permissions, then creates the account, assigns the
Space role and consumes a use atomically. Concurrent last-use redemption has one
winner. Role changes and disabled inviters fail closed on future acceptance.
Revocation is idempotent. Issuance is bounded to 20 requests per actor per minute;
registration failures use the existing per-username exponential backoff (process-local,
reset on restart). These controls do not replace a deployment ingress request limit. Expiration is computed server-side; no cleanup job is
required for correctness. Existing session/CSRF conventions apply: Web mutations
require a double-submit token, Core uses server-held bearer credentials. Important
changes are audited with actor, target and correlation ID, without invitation
credentials. Plaintext invitation recovery is intentionally unavailable.

## Tenant isolation coverage and limits

| Area | Boundary inspected | Status |
| --- | --- | --- |
| Identity/membership | Generated account Space FK; immutable membership trigger | Implemented, database integration tests |
| Roles | Workspace-scoped roles/targets; cross-Space assignment trigger | Implemented, existing/new integration tests |
| Invitations | Actor-derived Space; workspace/row locks; scoped revocation | Implemented, new integration tests |
| Rooms/integration credentials | Existing owner-scoped repositories and trusted request workspace key | Preserved; no global conversion |
| Local calendars | Service resolves `rbac.workspace(actor)`; owner predicates | Preserved; existing CRUD/IDOR tests |
| Conversations/memory | Personal account predicates in repository lookups | Preserved; existing personal separation tests |
| AI preferences/context | Personal actor ID; workspace policy derived through RBAC | Preserved; existing AI tests; not a full context-path certification |
| Device actions | Existing trusted owner passed to catalog/adapters | Preserved; full provider/IDOR audit remains incomplete |
| HA/calendar workers, gateway/voice, discovery, streams | Installation-global state and service credentials remain | Multi-Space runtime unsupported and startup guarded |

This change does **not** certify every device, WebSocket/stream, tool, worker,
integration, restore or AI retrieval path for concurrent Spaces. Core refuses
startup with more than one Space, and migration refuses ambiguous legacy roots.
Do not bypass that guard or insert Spaces through database administration in a
running instance. Multi-Space runtime requires a separate audited implementation.
Space suspension has no public endpoint; worker suspension semantics remain future
work. Database administrators remain trusted operators.

## Business identity and recovery

Milestone 02 adds optional SMTP mailbox proof, DNS TXT ownership challenges,
strict exact-domain policy with lockout prevention, and protected host-local OWNER
recovery. Local attestation is explicitly distinct from mailbox proof and cannot
satisfy strict policy. HOME stays unchanged unless an identity workflow is chosen.
See [Business identity and recovery](business-identity-and-recovery.md) for setup,
SMTP, expiry/re-verification and Linux/Docker/Windows procedures.

Business voice and unrouted AI proposals remain disabled pending per-person voice
principals and K-AI policy/budget integration. Multi-Space runtime remains guarded.
The [Milestone 02 tenant audit](spaces-tenant-audit.md) is the current coverage
statement; the initial matrix above describes the Milestone 01 baseline.

## Future portal and support: design only

`kyrion.ch` remains public product information. A future `portal.kyrion.ch` may own
licensing, installation registrations, billing, subscriptions/entitlements,
support requests and an optional invitation handoff. None supplies connectivity
to an unreachable local instance. Those future contracts reference the stable
Space UUID; no speculative subscription/support columns are added locally.

Future SUPPORT_OPERATOR identities are separate from customer identities. They
receive no global OWNER role or permanent customer membership. Customer-initiated
grants must be explicit, time-limited, scoped, revocable and audited; require MFA,
record approval/execution identities, and restrict sensitive data. No automatic
access to Velora memories, documents, secrets, credentials or private household
data is permitted. A separately reviewed secure relay may support reachable remote
sessions. Offline/local-only operation must remain independent of any portal.
No remote tunnel, support grant, bypass or privileged support API is implemented.

## Integration with parallel work

Changes are confined to the dedicated Spaces worktree. Shared touch points are
security classes, the authentication persistence test, Web setup/session proxy,
Settings, and the product page/locales. Reconcile migration number V37 and ADR
number 0031 before integration; never edit an already-applied migration to resolve
a numbering collision. Keep the legacy resource owner key until each consumer is
explicitly adapted. Do not merge or deploy without reviewing these boundaries.

Concrete integration note: parallel personal-context work currently owns V35/V36
and ADRs 0029/0030 in the original worktree. Spaces uses V37 and ADR 0031. The
parallel branch also modifies `AuthenticatedRouteInterceptor.kt` and `Rbac.kt`;
combine those changes intentionally and test the combined migration sequence.
