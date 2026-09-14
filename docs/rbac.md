# Role-based access control

Kyrion Core is the authority for installation-wide RBAC. Users may have multiple
roles and effective permissions are the union of all assigned role permissions.
The initial system roles are `OWNER`, `ADMIN`, `USER` and `VIEWER`; custom roles
are stored per installation and cannot replace or delete system roles.

Permission keys use `resource:operation`, for example `devices:execute`.
The permission catalog is seeded by Flyway migration V29 and is validated by
Core before role changes are persisted. The Web roles editor is only a client
for this catalog and is never a security boundary.

`OWNER` is enforced as a Core invariant: an owner has every catalog permission,
at least one active owner must remain, and the last owner cannot be disabled,
deleted or stripped of ownership. Deactivation keeps the account and all
historical data, revokes active sessions and blocks login. User deletion is
intentionally not exposed until a complete anonymisation policy for all
owner-scoped and personal data is defined; this avoids destroying audit history.

The first installation owner is assigned `OWNER` during setup. Existing users
are migrated to `OWNER` for the primary account and `USER` for invited accounts.
Fresh setup also creates the roles idempotently because the migration runs before
the first user exists.

The current model is intentionally installation-wide. Room, device and other
resource scopes are a future extension point and are not represented in the
current permission keys.

Core enforcement is applied by the authenticated route interceptor using a
central method/path registry. The registry covers activity, conversations,
memory, rooms, devices and device actions, gateways, voice, integrations,
backups, retention/system settings and RBAC administration. Controller-level
checks remain on the RBAC and invitation APIs. This registry is the consistency
check boundary: adding a new protected route requires adding its path family
and permission mapping; compile-time discovery of arbitrary controller intent
is not available in the current Spring MVC setup.

The Web receives effective permissions from `/v1/auth/me`, hides administrative
navigation and renders forbidden states, while Core remains authoritative for
direct API requests. Custom role edits, multi-role assignment, deactivation and
reactivation are exposed through the Web API and retain audit/session rules.

RBAC V1 deliberately does not implement hard user deletion, deny policies,
ACLs, external IAM, or room-, device- or resource-scoped permissions. These are
V2 topics and require separate data and policy decisions.
