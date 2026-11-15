# ADR 0089: Native Windows agent ingress maintenance

Status: Accepted for implementation

## Decision

Extend ADR 0088's existing transaction and Core approval to the native Windows
backend; do not introduce another journal or service manager. Recognize only the
exact managed native Caddy definitions. Use the existing pinned runtime,
protected file publication and owned SCM plans. Preserve the listener, TLS keys,
service identities and service dependency graph.

Use a bounded Windows DPAPI local-machine protected purpose/installation marker
for transaction host binding. It contains no account credential or device key.
Validate both DPAPI integrity and the exact recovered purpose/installation bytes.
This is host binding under the protected journal, not per-user authorization or
protection from a machine administrator. Existing native DACL checks still apply.

Pending native transactions use the same temporary installer journal format 2.
Both the native permissions helper and current runtime must recognize only the
explicit pending transaction shape. Verify the installed service host's native
ingress capability and manifest hash before mutation; a new downloaded installer
cannot replace an incompatible installed host implicitly. Enabled maintenance
workers must also support the existing transaction fence.

During new activation, only the owned Caddy role may start against the exact
approved replacement configuration. During original-configuration recovery,
Core, Web and Caddy may start only after the exact original bytes were restored.
All ordinary authority-retirement and update fences remain enforced. No role is
authorized merely by the presence of an arbitrary pending field. PostgreSQL's
existing native service is unchanged; no new database operation is introduced.

SCM can start dependencies when starting a dependent service. The review must
therefore identify possible startup of previously stopped owned dependencies;
it must not repeat Linux's proxy-only recreation claim. Preserve failed/pending
status if dependencies cannot start. Restoring file bytes alone is not successful
TLS recovery. Do not change service dependencies to manufacture an apparent
success while Core is unavailable.

Test pure policy and actual Windows DPAPI/ACL publication locally, then extend
the existing disposable elevated service fixture and manual CI workflow. Native
process tests cannot establish SCM, virtual-account or pre-login boot acceptance.

Official references checked before implementation:
[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata),
[CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata),
[StartServiceW](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-startservicew),
and [service dependency startup](https://learn.microsoft.com/en-us/windows/win32/services/automatically-starting-services).
