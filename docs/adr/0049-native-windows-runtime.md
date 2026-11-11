# ADR 0049: native Windows runtime with machine-start supervision

Status: accepted for implementation, 2026-11-11. This changes the Windows
runtime decision deferred in ADR 0045; it does not declare Windows provisioning
or cold-boot acceptance complete.

The downloaded installer will provision the existing Core JAR, standalone local
Web application, PostgreSQL and Caddy as native Windows x64 components in an
owned private directory. Core retains identical account, identity, Space,
integration and action contracts. Linux keeps its existing signed Compose path.
This is a runtime backend within the existing installer and journal, not a
second installer or another account/Space system.

Docker Desktop/WSL startup after interactive login is unsuitable for the normal
machine-start requirement. A native backend avoids imposing that limitation or
requiring a particular Hyper-V/desktop edition. Initial target candidates are
Windows 11 x64; concrete version acceptance must come from tests, not this ADR.
Unsupported/disabled Windows scheduling or missing administrator authority must
be diagnosed before mutation. No broad Windows support claim follows from a
native executable probe or XML schema test.

Runtime executables and application assets must come from an authenticated,
versioned native bundle with bounded extraction, exact file integrity, component
versions, original sources and licenses. Build the Web standalone payload on
Windows. Runtime ownership is private to Kyrion: do not replace a user's Java,
Node, PostgreSQL, Ollama or global configuration. Runtime prerequisites and large
downloads belong in the existing review/confirmation before changes.

PostgreSQL has its supported native `pg_ctl register/unregister` service path.
Core/Web/Caddy will use explicit machine boot tasks under the built-in Local
Service identity, not interactive logon triggers or a user's stored password.
Task names contain the installation UUID; registration must refuse foreign tasks
and maintenance must verify exact ownership before replacement/removal.
Use limited runtime privileges, explicit NTFS ACLs, bounded retries, duplicate
instance exclusion and actual dependency readiness. Executable/configuration
paths must be administrator-controlled. A controlled supervisor must contain its
children (Windows job object) so maintenance cannot leave competing writers.
No arbitrary command or untrusted environment-variable entrypoint is exposed.

Task tokens must explicitly contain their task-specific SID
(`ProcessTokenSidType=Unrestricted`). Grant runtime file access to those specific
task SIDs and the PostgreSQL service SID, not blanket access to Local Service;
unrelated services sharing the built-in account must not inherit access to
Kyrion secrets. Resolve and verify native SIDs after registration, prepare ACLs
before starting, and retain admin/System ownership of binaries and journals.
Fail closed if the SID/ACL setup cannot be established. Registration alone is
not a usable or accepted runtime.

Core and Web bind loopback. Caddy alone binds the reviewed private LAN address
with verified local TLS. Secrets remain protected files/environment/stdin, never
password-bearing command arguments. In particular, Core's existing database
secret loader reads process environment, so JVM command-line properties are not
a substitute for its `_FILE` contract. Do not inherit repository development
configuration in installed processes.

Resume, repair, backup, update and uninstall must dispatch through this backend
while preserving existing journal/identity and consent rules. Registration and
live readiness are distinct from an actual cold boot before login. Tests must
report which was performed. Only isolated developer resources may be registered
during development; no persistent tasks/services are created on the owner's
machine for acceptance.

Official documentation checked 2026-11-11:

- [Local Service task principal](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtaskprincipal?view=windowsserver2025-ps)
- [Boot trigger and administrator registration requirement](https://learn.microsoft.com/en-us/windows/win32/taskschd/boottrigger)
- [PostgreSQL 17 native service control](https://www.postgresql.org/docs/17/app-pg-ctl.html)
- [Windows child-process job containment](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Task-specific SID hardening](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-security-hardening)
- [Docker Desktop Windows permissions](https://docs.docker.com/desktop/setup/install/windows-permission-requirements/)

The built-in Windows scheduling APIs and Python's existing Win32 FFI avoid a new
third-party service-wrapper dependency. This choice requires native API tests,
explicit cancellation/recovery behavior and Windows runner/VM integration tests;
generated XML alone is not the finished user function.


Task definitions also require administrator/System-only protected task ACLs.
An exact command/principal match alone does not prevent a lower-privilege task
owner from replacing it after validation. Native registration supplies a fixed
protected security descriptor, suppresses the automatic principal ACE, and
validates the resulting descriptor on every existing-task operation. No broad
Local Service task-management permission is added. This follows the official
[RegisterTaskDefinition contract](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertaskdefinition).
