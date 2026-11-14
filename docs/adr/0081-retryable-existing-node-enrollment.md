# ADR 0081: Retry acknowledgement in existing node enrollment

Status: Accepted for implementation, 2026-11-14.

Installer devices must reuse Core's existing gateway-node identity, enrollment
and Space authorization. Creating a separate installer account, node credential
store in Core or second pairing authority is rejected. Existing specialized
gateway/voice paths remain compatible. This decision addresses an immediate
failure case before extending roles and agent lifecycle: a node registration
response may be lost after Core consumes its one-use enrollment token.

For a new opt-in enrollment variant, the prepared local agent generates and
protects its own 256-bit random node credential before transmitting the existing
pairing request over verified local TLS. Core stores only its existing hash.
Legacy agents may continue to receive a server-generated random credential.

Bind a successfully created gateway node explicitly to its consumed enrollment
row with a nullable unique foreign key. Existing nodes keep a null association;
no guessed backfill joins timestamps or hostnames. A retry is an acknowledgement
of that same node only: it must present the same pairing token, the same agent
credential and identical original identity fields, and remain inside the
enrollment's original expiry. It never creates another node or consumes the code
for a different claimant. Wrong credential, changed identity, expired code,
legacy enrollment replay and cross-Space access fail with the existing generic
enrollment error. The retry rechecks the existing tenant boundary.

The association also constrains the existing owner/Space. PostgreSQL 17's
column-specific `ON DELETE SET NULL (enrollment_id)` preserves node/owner identity
when the existing restore/recovery disposition removes enrollment rows and
rotates node credentials. No user identity is nulled or deleted by that cleanup.

Expose a bounded protocol-capability response from the existing gateway-agent
controller. Prepared clients must verify protocol 2 before transmitting the
code/credential. Older servers may ignore unknown JSON fields; sending the new
credential to such a server could otherwise create an unrecoverable registration.
Existing server-generated enrollment remains protocol-compatible for old agents.

Keep creation and code consumption transactional, preserving the current atomic
one-use SQL update. A concurrent duplicate can acknowledge only the committed
associated node. Agent credential/pending state is local and protected; it is
not a command argument, log field or browser response in owner listings. After
expiry, retries require explicit authorized enrollment recovery rather than
silently weakening the expiry. No token refresh or indefinite pairing window is
introduced.

This is a compatible extension of existing enrollment, not completed installer
multi-device setup. Role distribution, revocation, least-privilege agent runtime,
TLS transport exposure, offline coordination and writer-safe moves remain
separate implementation and test requirements in the binding installer ledger.
