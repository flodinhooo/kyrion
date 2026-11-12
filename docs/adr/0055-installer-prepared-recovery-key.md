# ADR 0055: Installer-prepared Windows recovery material

Status: accepted for implementation, 2026-11-12.

Windows file ownership defaults to the creating user, even when the parent has
an inherited private DACL. That user can later change the DACL as owner. The
installed native profile requires recovery material owned by Administrators and
accessible only to Administrators/SYSTEM, outside runtime service access.

The elevated installer exclusively creates a private recovery directory and
host key with their final owner/DACL at creation. It journals the key digest and
Space ID before launching Core. A new host-console-only `provision-prepared`
mode reads that existing protected file and invokes the same LocalOwnerRecovery
transaction/password/audit policy as `provision`. It never creates another
identity, HTTP recovery endpoint, or credential database. It preserves prepared
material on failure; a retry uses the exact recorded key. A code lost after a
successful database commit requires explicit rotation with the OWNER password.

Installer maintenance exposes the existing open/complete/rotate commands. All
secrets and recovery codes remain in the inherited real Core console, never
command arguments, installer output capture, or progress journals. Validate
service ownership before stopping any services, leave PostgreSQL running, and
restart runtime services in a finally block. Mock orchestration tests do not
constitute elevated ACL, interactive-console or cold-boot acceptance.
