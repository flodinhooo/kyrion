# ADR 0019: Shared installation registration

- Status: Accepted
- Date: 2026-09-06
- Supersedes: ADR 0002's restriction to one account

## Context

The owner requests additional accounts so a friend can control the same local
installation, with RBAC explicitly deferred. Creating isolated device catalogs
would not meet that requirement.

## Decision

Core provides invitation-based registration at `/v1/auth/register`. Each account has
its own password, session credentials and identity. Registration joins the
installation resource scope of the authenticated inviter. Setup remains a one-time
compatibility endpoint. Account creation is serialized with the same database
transaction as invitation redemption; normalized usernames remain unique.
The original resource owner explicitly creates a random, single-use invitation in their
profile. Only its SHA-256 hash is stored. It expires after 24 hours. Redemption,
account creation and session issuance are atomic. Invalid, expired and redeemed
codes return the same error without creating an account.

A nullable `workspace_owner_id` on an account identifies its shared resource
scope; null retains the existing account's own scope. Existing resource rows
and their audit seals are not rewritten. New accounts join the inviter's scope,
which is stored with the invitation and never accepted from browser input.
There is currently no account deletion or workspace transfer endpoint.

Authenticated shared controllers use a separate server-derived workspace
attribute for devices, rooms, integrations, gateways, satellite management,
actions and the shared activity feed. Authentication identity is never replaced.
Chats, personal memory, personal backups, retention and session/password
management continue to use the individual account ID.

All registered accounts can manage shared resources equally. This is an
explicit interim policy, not RBAC. The signup page explains the granted access;
only holders of a valid invitation can join after initial setup. Invited accounts
cannot create further invitations; Core enforces this narrow enrollment policy
independently of shared device-management access. Internet
exposure, account administration and granular roles remain outside this change.

Audit recording resolves the authenticated HTTP actor independently from the
resource scope through a small actor-source interface. Explicit action contexts
also retain the real actor, including in idempotency hashes. Gateway completion
events retain their integration identity and correlation with the user request.

## Consequences

Friends see and control the existing devices without sharing credentials.
Core validation, command policy, confirmations, session security and protected
provider credentials remain in place. Future RBAC can authorize the actor against
the resource scope instead of conflating the two identities.
