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

Existing-Space invitations reuse the same proof mechanism and the existing Core
invitation authority. A separate operation purpose binds the invitation's hash;
completion atomically redeems it through LocalAuthenticationService.register
and creates the identity link. Membership, expiry, use limits, email policy and
delegated role are still checked at redemption by the existing Space code. A
duplicate central link rolls back both account creation and invitation use.
Neither regular LOGIN completion nor setup completion can redeem this purpose.

An expired installer-owned bootstrap file must not permanently strand an
unfinished installation. An explicitly confirmed privileged host operation may
extend the existing unused credential's timestamp window for Core's existing
30-minute verification policy. It first requires Core to report setup pending
and refuses journals that expect an established owner. It changes no credential
bytes, inode, permissions or identity; Compose's read-only secret bind therefore
continues to reference the same file. A pending journal intent fixes the renewal
timestamp across interruption/retry. OAuth proofs keep their independent expiry,
single-use and bootstrap/session binding. Core's transactional owner lock remains
the authority if setup completes concurrently. No automatic indefinite extension
or bootstrap recovery for a lost established owner is introduced.

Windows sets last-write time through a non-reparse handle with
FILE_WRITE_ATTRIBUTES; Linux uses a no-follow timestamp update. Reference:
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfiletime
