# ADR 0031: Local Kyrion Spaces and compatibility ownership

Status: Accepted for the single-Space MVP; multi-Space runtime remains gated.

A Space is HOME or BUSINESS product configuration. Ordinary identities belong
to exactly one Space. Home and company identities remain separate. Core owns
membership, invitations and authorization; the public website has no authority.

Preserve the existing workspace owner UUID as the Space UUID and compatibility
resource partition key. Do not rewrite encrypted credentials, personal ownership,
audit chains or historical records. A generated account Space ID and foreign keys
make membership explicit. Roles derive their Space from installation_owner_id.
Database constraints reject role assignments across Spaces and membership moves.

Legacy migration requires one enabled root workspace owner, valid same-workspace
roles, and no nested workspace ownership. Ambiguity aborts with an operator
diagnostic. Never select a company type from an email address. Existing data uses
a HOME Space, which the owner may configure. No applied migration is edited.

First setup retains the protected local secret and serialized durable bootstrap.
Space configuration and OWNER creation commit in the same transaction. Existing
API clients default to HOME with a local Space name. Invitations retain hashed
opaque codes and add bounded uses, revocation and role selection. Redemption locks
the invitation row; role delegation and redemption serialize with RBAC mutations.

The existing installation contains globally shared discovery and worker state.
Until every background, gateway, voice and AI path supports multiple tenants,
Core must refuse startup with more than one Space. This is a deliberate runtime
guard, not a claim that those subsystems are multi-tenant safe.

Business domain enforcement requires verified email and domain ownership. Current
authentication has usernames, not verified email identities. Do not invent proof
from an email string. Domain enforcement remains unavailable until verification
and a protected local recovery workflow exist.
