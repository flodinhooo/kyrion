# ADR 0053: Linked first-owner setup and authorized Space selection

Status: accepted for implementation, 2026-11-12.

The installer product request supersedes optional post-setup linking as its
normal onboarding path. Existing local installations retain independent local
login and optional linking; no existing account is migrated or silently linked.

Extend Core's existing RFC8628 operations with first-owner setup bound to the
installer-owned bootstrap secret. Verify that secret before upstream work and
on each setup operation. Only its hash binds the in-memory operation. Provider
proof precedes local account creation. A dedicated completion transaction reuses
LocalAuthenticationService.setup and inserts the central identity link, with
Space, roles, local password hash, session and audit in the same transaction.
Failure consumes the proof and rolls back all local creation. A provider claim
alone never authorizes ownership; the protected installation bootstrap does.
Normal LOGIN/LINK completion must reject setup operations.

Offline credentials belong to that same linked local identity. Never ask for a
website password or persist operation credentials in installer progress. Pending
proofs are intentionally abandoned on Core restart; users resume with a new proof.

Preserve the current audited one-Space-per-Core boundary. Fresh setup explicitly
creates HOME or BUSINESS. Existing installation onboarding authenticates through
the existing identity mapping and offers only its authoritative current Space,
showing membership/roles before configuration. Do not fabricate a global Space
directory or bypass the multi-Space guard. Joining a Space on another prepared
Core needs authenticated device enrollment, tracked separately in R23-R29/R35.

The downloaded installer owns this flow. The browser only handles provider
authentication. Provider configuration is public operator/release configuration;
no shared customer client secret or public callback endpoint is introduced.
