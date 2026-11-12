# ADR 0050: dedicated native Windows service identities

Status: accepted for implementation, 2026-11-12. Supersedes the boot-task portion
of ADR 0049 before any owner-host task registration or production release.

The native backend remains part of the same downloaded installer, signed native
payload, installation journal and Core authority. Core, Web and Caddy run through
a native Service Control Manager (SCM) host implemented with the existing Python
Win32 FFI and child job containment. PostgreSQL uses its supported pg_ctl native
service registration. Each service uses its own passwordless virtual account
`NT SERVICE\Kyrion-<installation UUID>-<role>`; no LocalSystem application service,
shared Local Service account, user password or login startup is introduced.

Task-specific access rules do not eliminate all complexity of a shared service
account and a one-file frozen worker's extraction lifecycle. Dedicated virtual
accounts provide separate account/owner SIDs as well as service SIDs. SCM also
expresses actual PostgreSQL -> Core -> Web -> Caddy dependencies and service
shutdown. The prepared task helpers remain auditable development groundwork,
not a second active runtime. No task/service registration is performed on the
owner's machine as acceptance; use disposable Windows CI/VM environments.

Create a private administrator/System-owned installation root atomically before
secrets. Public payload/executable/config is read-only to runtime identities;
only the relevant identity can modify its data directory. Core alone reads its
credential/bootstrap/database secret files; Caddy alone reads TLS private keys.
Validate ancestor ownership and replacement rights as well as the leaf ACL.
Refuse foreign service names/definitions, path changes, noncanonical UUIDs,
wrong accounts, unsafe DACLs or changed managed binaries before mutation.

The installed frozen entrypoint dispatches fixed roles, not arbitrary commands.
It reports START_PENDING/checkpoints while validating and waiting for actual
readiness, RUNNING only after a real health check, and STOP_PENDING/STOPPED for
shutdown. Stop/cancellation closes the noninheritable job and its descendants.
The backend persists progress in the existing installation journal, preserves
keys and data on resume/repair, and stops dependants before their database.
SCM failure recovery is bounded and does not include a cloud fallback.

Verify parser/domain behavior and native SCM dispatch separately. A running
process or mocked SCM is not boot acceptance. Prepare actual service lifecycle
and account/ACL acceptance on disposable Windows runners; cold boot before login
and supported stable Windows versions remain explicit target acceptance gates.

Official references reviewed 2026-11-12:

- https://learn.microsoft.com/en-us/windows/win32/services/service-user-accounts
- https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-startservicectrldispatcherw
- https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-createservicew
- https://www.postgresql.org/docs/17/app-pg-ctl.html

PostgreSQL initialization must also run as its dedicated virtual identity.
`initdb` refuses an administrator token; granting the interactive user access to
the protected database directory would weaken the runtime boundary. A temporary
fixed installer-host service occupies the same PostgreSQL service name/account
only during initialization, with demand start and no automatic retries. It can
read only the temporary password grant and write the owned pending database and
initialization status directories. After success, the elevated installer verifies
the control data, removes the bootstrap service, promotes the directory, revokes
the password grant, and registers PostgreSQL using supported pg_ctl. No two
postmasters or initializers run concurrently. Interrupted bootstrap data is
preserved; a running initializer is never renamed out from under its process.

The downloaded bootstrap remains a one-file executable, but installed SCM hosts
use a frozen one-directory program included in the signed native runtime
bundle. This avoids relying on a one-file bootloader's parent/child startup and
runtime extraction during SCM connection. Native manifest schema 3 adds the
versioned installer-host component and its license/hash inventory; schema 2
remains verifiable for historical developer payloads but cannot provision SCM
services without that component. The host's entire public program directory is
read-only to runtime identities. A supported older installer can use an updated
compatible published service-host component instead of retaining its own old
embedded worker implementation.

Internal transport authenticates endpoints, not just loopback addresses. Core
uses Spring Boot PEM HTTPS with a dedicated protected key. Installer clients pin
its certificate; Web receives process-scoped NODE_EXTRA_CA_CERTS. No global trust
store changes or disabled verification are required. The Web SCM host terminates
a separate loopback TLS endpoint and forwards to its contained Next.js child
only after the Windows TCP ownership table proves the established connection
belongs to that child PID. Caddy pins the Web certificate. The transport host
accepts no caller-selected destination and contains no business rules.

Transport references:
- https://docs.spring.io/spring-boot/appendix/application-properties/
- https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getextendedtcptable

Installer file publication must retain the same identity boundary as directory
creation. A temporary journal or new managed file is exclusively created using
CreateFileW with the existing file's or protected parent's owner/group/DACL in
SECURITY_ATTRIBUTES. The existing journal's policy is copied before replacement;
the owner and protected DACL must survive every save. Creating a file as the
interactive administrator and only fixing its owner afterward leaves an
unnecessary owner-policy window and is not the publication contract. Runtime
status files remain ordinary writes inside their dedicated identity directories.
