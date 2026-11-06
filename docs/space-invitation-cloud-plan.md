# Personal Space invitation via kyrion.ch — implementation contract

Status: next implementation slice, **not implemented** by identity integration.
No additional invitation authority, general remote access or data synchronization
is introduced. Core remains the membership authority. HOME/single-Space only.

## Existing implementation to extend

`SpaceService.createInvitation` already authorizes `invitations:create` under
the workspace lock, validates the selected local role/delegation, excludes OWNER,
accepts an optional normalized target email, and persists a random 256-bit code's
SHA-256 digest, expiry, revocation, usage limit and role. The existing endpoints
are `POST/GET /v1/space/invitations`, `DELETE /v1/space/invitations/{id}`.
`JdbcUserAccountRepository.registerVerified` locks the workspace and invitation,
rechecks Space/inviter/role/delegation/expiry/usage, validates enrollment proof,
creates the password-protected account, assigns its non-OWNER role and consumes
the invitation atomically. Local `/signup#invitation=...` removes the fragment.
`BusinessIdentityService.enrollment` currently accepts **local SMTP proof**, not
an arbitrary provider email claim. `central_identity_link` uniquely binds local
user to `(issuer, subject)`; no email-based account search/merge exists.

Reuse these records, mutation locks, business rules and audit transactions.
Extract the common invitation eligibility/consumption operation so local signup
and a confirmed central-invitation completion call the same authoritative policy.
Do not implement a second cloud membership or role store.

## Required identities and installation enrollment

Each participating installation generates its own non-exported key pair and
registers its public key through **explicit local OWNER approval**, authenticated
local session, fresh local password and a freshly confirmed central identity.
The broker assigns an opaque installation UUID and a narrowly scoped mTLS client
certificate. Provisioning must bind a broker challenge to that public key and
the local installation/Space, with both sides confirming the pairing. Never ship
a common private key/client secret. Revoke/rotate a registration locally; a
central account alone cannot register or take over an existing installation.

The certificate authorizes only invitation publication, polling, receipts,
acknowledgments and revocation for that installation. It grants no device/API,
shell, resource or user-data access. The installation opens outbound HTTPS on
443 to the broker and polls; no inbound public/LAN callback is required. A
separate central service/broker is needed; the static website and its current
account-session tables do **not** provide that infrastructure today.

Pairwise OIDC subjects are an explicit prerequisite. Add a provider-maintained,
immutable opaque `kyrion_account_id` claim to the broker/website and local device
clients. Keycloak must provision it and prohibit self-service edits; an ordinary
user-editable profile attribute is unacceptable. Audit/backfill it through
trusted provider administration, never email matching. The central broker uses
this provider-confirmed UUID to correlate its website proof with a fresh local
device proof. It must never assume two clients' `sub` values are equal.

Keep `(issuer,sub)` as the local authentication key. Extending an existing link
with the central UUID requires **new authenticated provider proof for that same
link**. No import based on an asserted browser UUID, username or matching email.
Only transfer this additional identity value with explicit invitation/link consent.
Without trusted cross-client mapping, completion returns
`CENTRAL_ACCOUNT_MAPPING_REQUIRED`; do not weaken identity verification.

## Minimum central metadata

| Record              | Fields and authority                                                                                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Installation        | Opaque installation UUID, registered public key/certificate status, protocol version; locally approved pairing is authority                                                                                                                 |
| Invitation envelope | Installation UUID, opaque local invitation UUID, SHA-256 capability digest, version, expiry, revoked flag, target-email HMAC, optional explicitly released Space display name and role label; Core owns all mutable facts                   |
| Acceptance          | Random acceptance UUID/idempotency key, invitation/version, provider issuer and verified central UUID, consent/authentication timestamps, target-email proof, acceptance deadline and state; provider owns identity, recipient owns consent |
| Delivery result     | Acceptance UUID, request digest, local result/revision and completion timestamp; Core is authority                                                                                                                                          |

Do not upload role permission sets, local usernames, passwords/hashes, local user
catalogues, devices, calendars or other user content. The broker receives target
email transiently over TLS to compute a keyed HMAC and may show a masked address;
do not retain plaintext email unless a later delivery feature explicitly needs it.
Owner **copies and sends the link themselves**; this slice sends no invitation mail.
Central email verification is performed by Keycloak. Define normalization to match
`BusinessAddress.email`: IDNA/lowercase domain, preserved local-part case, exact
match. Case mismatch means correction/new invitation, never guessed equivalence.

## Owner and recipient flow

1. OWNER creates a personal, email-constrained **one-use** existing local
   invitation with a non-OWNER role. Publication intent plus local invitation
   are committed with an outbox record and correlation UUID. Broker publication
   is idempotent on `(installation,invitation,version)`; only an acknowledged
   envelope produces the ready-to-copy public link. If offline, show “publication
   pending”; offer the existing local link separately with its actual reachability.
2. Copy `https://kyrion.ch/invitations#code=<existing random capability>`.
   No token in query/path/referrer. Portal removes the fragment immediately and
   posts the code once; broker hashes it, discards plaintext and binds an opaque,
   HttpOnly, CSRF-protected invitation-flow cookie. Do not put invitation codes
   into OIDC `state`/`redirect_uri`, localStorage or logs. State/nonce/PKCE stay
   independent. Fixed callback resumes the stored **allowlisted invitation route**.
3. Recipient logs in or registers through Keycloak. Verification email returns
   to the same bounded invitation flow. Reauthenticate if the portal session,
   flow or identity proof expired. Require `email_verified=true` from a fresh
   provider proof; do not accept an unchecked editable website profile field.
4. Broker compares the verified address with the target constraint. Wrong account
   gets `INVITATION_ACCOUNT_MISMATCH`, masked target and a sign-out/switch-account
   option; do not expose Space membership or consume the invitation. Resumption
   retains the invite but never reuses another account's consent.
5. Show the deliberately released installation/Space/role labels and require
   explicit acceptance. POST with CSRF and stable random idempotency key creates
   one bounded acceptance. A duplicate identical request returns its existing
   state; changed identity/content under the same key is `IDEMPOTENCY_CONFLICT`.
6. The installation polls and receives a **purpose-specific signed acceptance
   receipt**, not a general access/ID token. It validates trusted broker signature,
   fixed algorithm, issuer, audience=installation UUID, purpose, local invitation
   UUID/digest/version, identity and proof freshness, consent, receipt nonce and
   expiry. It then rechecks the actual local invitation and current authorization
   under the existing workspace/row locks. A receipt is never membership authority
   on its own. Commit consumption, local result/idempotency row, link/member
   changes (where permitted) and audit atomically, then acknowledge to the broker.

## The local-password and single-Space gate

Current accounts always belong to exactly one Space and require an Argon2id
local password. A remotely accepted invitation cannot silently bypass those
rules. Recommended completion cases:

- **Existing linked local member of this Space:** return `ALREADY_MEMBER` with
  the existing local user UUID, consume this personal acceptance once, and change
  no roles. A different requested invitation role never upgrades an existing user.
- **Existing unlinked local member:** state `LOCAL_LINK_REQUIRED`. Recipient must
  log in locally, reauthenticate and complete the existing explicit central link.
  Resume only after fresh trusted UUID mapping identifies that same local user;
  then return `ALREADY_MEMBER`. Never discover/merge users by email or username.
- **New local user:** state `LOCAL_ENROLLMENT_REQUIRED` until the recipient can
  reach the local Web and choose their local username/password. Use a bounded
  acceptance reference plus fresh central proof to complete the existing
  invitation registration transaction and explicit linking together. Password is
  sent only to local Core. Create user, its sole membership, selected role, link,
  invitation consumption, idempotent result and audit in one transaction.
- **Identity already attached to a different local user/Space:** reject with
  `IDENTITY_ALREADY_LINKED` or `MULTI_SPACE_UNSUPPORTED`. No move, duplicate
  identity, second membership or Space switcher is enabled.

Consequently an entirely remote new recipient without LAN access remains pending
even if Core is online. This is a necessary local-credential step, not an excuse
to upload their password to kyrion.ch or add remote device access. The portal
must distinguish it from `INSTALLATION_OFFLINE`. If the desired product flow
requires immediate remote-only account creation, that needs a separate reviewed
local-login design; this plan deliberately retains the current security model.

HOME-only enrollment may accept the broker's verified-email receipt through a
new explicitly typed `CENTRAL_OIDC` proof source. Do not mark it as local `SMTP`.
Business STRICT rules continue to require their current proof; return
`BUSINESS_CENTRAL_ENROLLMENT_UNSUPPORTED` until a dedicated policy review and
tests authorize a central proof method. Central email never grants domain control.

## Proposed versioned contracts (future, not current endpoints)

All bodies are bounded typed JSON. Installation calls use mTLS; recipient calls
use the existing central BFF session plus CSRF. Do not accept arbitrary URLs.

| Endpoint                                                                   | Request/result                                                                                                                                                   |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PUT /v1/installations/self/invitations/{invitationId}`                    | `version, capabilityHash, expiresAt, targetEmail, display?`; idempotent publication; same-version altered body conflicts                                         |
| `POST /v1/invitation-flows`                                                | Capability in body once; issues HttpOnly flow cookie and safe display/status                                                                                     |
| `POST /v1/invitation-flows/current/accept`                                 | `idempotencyKey, confirm:true`; server obtains fresh verified identity, never accepts caller-chosen recipient UUID                                               |
| `GET /v1/invitation-flows/current/status`                                  | Allowlisted state, required next step, expiry; no local credential/token                                                                                         |
| `GET /v1/installations/self/invitation-acceptances?cursor=...`             | Bounded at-least-once mailbox of signed receipts; only this registered installation                                                                              |
| `POST /v1/installations/self/invitation-acceptances/{acceptanceId}/result` | Signed/authenticated `requestDigest, result, localUserId?, committedAt, invitationVersion`; retry-identical result is safe                                       |
| `POST /v1/space/invitations/acceptances/{acceptanceId}/complete` (local)   | Fresh local proof / local username+password as applicable, explicit consent and broker receipt reference; uses existing policy and atomic membership transaction |

Receipt claim set: `iss, aud, iat, exp, jti, purpose=kyrion.space.join.v1,
installationId, invitationId, invitationVersion, capabilityHash, acceptanceId,
centralIssuer, centralAccountId, verifiedEmail, emailProofObservedAt, consentAt`.
`emailProofObservedAt` is the broker's timestamp for observing a fresh provider
`email_verified` claim; it does not invent the original mailbox-verification time.
Use a maintained JOSE validator and separately pinned/configured broker keys;
never fetch signing keys from receipt-supplied URLs. These receipts are scoped
commands validated by Core, not a new OAuth server or general API tokens.
Keep receipt lifetime short (five minutes), acceptance lifetime bounded by local
invitation expiry, and refresh delivery proof only for the original confirmed
recipient/consent while still eligible. After long offline periods require fresh
provider/email confirmation before issuing a new receipt.

## States, races and retries

Local invitation remains `ACTIVE/USED/REVOKED/EXPIRED` using the current fields.
Transport/acceptance states are additional **delivery state**, not invitations:
`PUBLISH_PENDING → AVAILABLE → ACCEPTED_PENDING → DELIVERING → COMMITTED`;
`LOCAL_LINK_REQUIRED`/`LOCAL_ENROLLMENT_REQUIRED` may interrupt delivery;
terminal outcomes include `ALREADY_MEMBER`, `REVOKED`, `EXPIRED`,
`ACCOUNT_MISMATCH`, `IDENTITY_CONFLICT`, `POLICY_DENIED`.

- Installation offline: retain `ACCEPTED_PENDING`, never display joined/success.
  A liveness timestamp is an observation, not proof the installation is online.
- Revoke/expiry while pending: Core's transaction-time checks always win, even
  if broker mirror is stale. Revocation publishes a higher-version tombstone via
  outbox. Expired/revoked acceptances cannot be revived by a receipt or retry.
- Role/inviter/account/Space changes: re-evaluate at completion. No stale cloud
  snapshot restores permission. OWNER invitations remain forbidden.
- Crash before local commit: retry delivery. Crash after commit before ack:
  `(installation,acceptanceId)` durable result plus request digest returns the
  same success without consuming another use or recreating the account.
- Connection loss during signup: return the stored result only after proving the
  same recipient/local account. Never return an old raw session credential from
  an idempotency cache; issue a fresh session through ordinary authentication.
- Polling uses bounded exponential backoff+jitter and durable cursors; acknowledgments
  occur after commit. Deduplicate receipts by acceptance ID/digest, not email.
- Shared links have no membership value for a mismatched verified account. Single
  use and target identity are checked again locally. Central/local audit records
  share a correlation UUID, without capability, password or email in summaries.

## Next implementation order and acceptance

1. Agree the provider-owned central UUID claim, explicit installation pairing,
   broker key/certificate lifecycle and HOME local-enrollment gate above. Add ADR
   and typed contracts; no placeholder public service should be called deployed.
2. Extend existing invitation policy with shared atomic redemption, typed
   proof-source policy, durable completion idempotency and local outbox/inbox via
   new additive migrations. Existing local-only invitations must stay unchanged.
3. Implement minimal central mailbox/BFF invitation resumption, verified-account
   comparison, explicit acceptance and pending UI. No general resource tunnel.
4. Implement outbound-only polling and local link/enrollment completion UI. Then
   test existing/new central accounts, same/different local members, wrong account,
   expiry/revoke/role changes during every phase, duplicate/racing requests,
   crash-after-commit, long offline reproof, strict Business denial and unchanged
   single-Space/OWNER protections against real provider/mail/Core/browser services.
