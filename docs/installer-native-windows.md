# Native Windows runtime bundle (development)

The native payload contract from ADR 0049 now feeds the executable SCM backend
in [ADR 0050](adr/0050-native-windows-services.md). `native_runtime.py` implements
private journal publication, signed staging, initialization under dedicated
virtual service identities, activation, readiness, repair and removal. This is
not completed consumer Windows support: actual privileged service/ACL and boot
acceptance remain outstanding, and the full product journey has open source work
in the [requirements ledger](installer-requirements.md).

## Build and trust

`release/build-windows-bundle.py --profile <clean-profile> --metadata <json>
--output <new-directory>` produces `manifest.json` and
`kyrion-windows-amd64.zip`. It never downloads dependencies or publishes a release.
The profile contains Windows-built standalone Web assets, existing Core/parser
JARs and dedicated Java 21, Node 22, PostgreSQL 17 and Caddy runtimes. Never copy
`.env`, a developer checkout, links, private keys or personal runtime data into
that profile. Include original licenses/notices in `licenses/<component>.txt`.
Kyrion currently has no selected repository license: its development metadata
uses `LicenseRef-Kyrion-All-Rights-Reserved` and a null license URL, without
inventing redistribution permission.

The schema-3 manifest records exact component versions, HTTPS source/license
metadata, API/schema/PostgreSQL-major compatibility, archive size/hash and every
file size/hash. The builder validates its completed archive before writing the
new output directory. Signing is a separate release-authority step, using the
existing detached Ed25519 `manifest.sig` contract. An independently trusted
public key is required; a key included beside a download is not itself a trust
anchor. Production trust distribution/signing remains outstanding.

Schema 3 includes the one-directory frozen `runtime/installer/kyrion-service.exe`
host and its complete dependency/license inventory. Schema 2 remains verifiable
for historical developer payloads but is refused for SCM installation. Build the
downloadable one-file executable with `release/build-native.py`, the installed
host with `release/build-native-service-host.py`, then assemble the profile using
`release/assemble-windows-profile.py`. The latter accepts only pinned verified
vendor archives and explicit clean application/host build directories.

Normal roles use separate virtual accounts; bootstrap `initdb` temporarily uses
the PostgreSQL account before supported `pg_ctl register` replaces it. Services
have explicit administrator/System management ACLs, bounded recovery and fixed
dependencies. A temporary bootstrap service never automatically retries an
initializer. The installed host verifies role payload hashes and negative secret
and writable-code boundaries before launching its contained process tree.

Core and Web each have distinct internal TLS keys/certificates. Core clients pin
the certificate; Node uses process-scoped extra trust. Caddy pins the Web host's
certificate; that host checks the established TCP peer belongs to its own Node
child before forwarding request bytes. No TLS-verification bypass is installed.

Private download staging is journalled and checks archive/manifest hashes again
after copying; it never extracts directly from a mutable original download.
Interrupted archives are preserved and never adopted without verification.

Signature verification returns the exact verified manifest bytes. Review and
provisioning bind their digest to those bytes, rather than reopening mutable
metadata after signature verification. Linux image input is copied into the
owned installation's private staging area and rechecked before Docker receives
it; source/download paths are never given to Docker after review.

## Extraction and resumption

`native_bundle.unpack(bundle, trusted_key, destination)` validates all input
before destination mutation, takes the existing cross-platform exclusive
installation lock and refuses an unowned destination. It bounds metadata,
archive expansion, file count and per-file size. It rejects path traversal,
Windows case aliases/reserved names, private configuration, symlinks and unknown
archive entries; PE executables/libraries must be AMD64. It never executes them.

The owned root receipt binds destination and manifest hash. Each member is
written exclusively, hashed, fsynced and promoted with an exclusive hard link.
Repeated runs recheck every existing file and refuse altered content. Partial
public files and interrupted atomic-journal temporaries are preserved outside
the application tree and never adopted as configuration or secrets. Receipt
format 2 uses a compact informational progress count; validated format-1 lists
migrate without weakening file checks. `complete` is set only after every file
passes. Return values explicitly report `runtimeActivated: false`.

## Developer verification

`tests/test_native_bundle.py` uses signed synthetic ZIP/PE bytes without launching
an executable. It covers strict schema/paths, real signatures, tampering,
interruption/resumption, legacy receipt migration, exclusive locking and build
output preservation. These are not Windows service acceptance tests.

`tests/integration/verify-native-windows.py` additionally runs the real verified
native payload, with a fresh synthetic database and random loopback ports. It
checks Core migrations/owner/Space, trusted TLS Web, and local login after
Core/database process restart. It creates no services or scheduled tasks and
cleans up only its own processes/data. It requires Windows, the prepared signed
development bundle, its independently supplied test public key, and OpenSSL:

```powershell
python infrastructure/installer-v1/tests/integration/verify-native-windows.py `
  --bundle <bundle> --key <trusted-test-public.pem> --payload <owned-payload> `
  --work-parent <existing-private-development-directory> --report <report.json>
```

This process-level fixture is not network-isolated and establishes neither
machine boot before login nor the intended Local Service/task-SID ACLs. No
published consumer support or public artifact availability follows from it.


## Child containment

`windows_process.py` starts the native child suspended, assigns it to an unnamed
noninheritable Windows job with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, and only
then resumes its primary thread. Assignment/resume failure terminates the
suspended child and closes its handles. Closing the owner ends the descendant
tree; an owner crash closes the job handle through Windows. No blanket PID/name
process kill or breakaway flag is used. Native FFI follows the Microsoft
[job object contract](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
and [suspended assignment requirement](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject).
Two actual Windows tests verify child/grandchild termination after deliberate
close and after an abrupt supervisor exit. The native SCM host now uses this
module; no boot/service acceptance is claimed by these process tests.


## Current platform evidence (not consumer support approval)

| Platform | Actual developer evidence | Outstanding acceptance |
| --- | --- | --- |
| Windows x64, build 10.0.26300.0 | 125 tests (one symlink skip); new one-file and one-directory builds; real Core/Web/PostgreSQL/Caddy with pinned internal TLS, verified Node peer and restart login | Actual service registration/virtual-account ACL normalization; supported-version/cold-boot acceptance; complete product journey |
| Debian 13 x64 | 125 tests (13 platform skips) in separate WSL guest with drive mounts/interop disabled; historical standalone smoke, source stack and encrypted restore evidence retained | Full installed host boot/maintenance and complete product journey |
| Linux ARM64 / suitable Raspberry Pi | Native build jobs prepared; bounded inventory/manifest contracts tested | Actual native artifact build, target installation and hardware/boot acceptance; no current release claim |

The successful native stack uses Java 21.0.13+9, Node 22.23.3, PostgreSQL 17.11-5
and Caddy 2.10.2. PostgreSQL helpers must not use captured output pipes for daemon
startup: inherited pipe handles can outlive the helper and block completion.
The fixture writes helper output to local synthetic logs instead. Core key
files contain 32 raw random bytes. The developer sandbox's restricted token
cannot create PostgreSQL's own restricted token; the passing process test used
the normal developer execution context without registering services/tasks.


The task helper also protects task management itself with an explicit
administrator/System-only protected DACL; matching executable arguments is not
sufficient ownership evidence. It rejects weaker existing task descriptors
instead of adopting/rewriting them. Native descriptor tests cover ten unsafe
variants without registering a task. Actual scheduler registration/normalization
and boot acceptance must still run on a disposable supported Windows target.


Ancestor-path hardening also refuses privileged task operations beneath
untrusted-owned or user-replaceable parent directories, even when the immediate
installation root is protected. It checks effective ancestor ACLs and rejects
write-data/reparse, deletion and ownership/DACL replacement rights outside
System/Administrators/the resolved Windows TrustedInstaller identity. Eight
native in-memory directory-policy cases pass; the test changes no actual file
ACL. Real installed-directory/service acceptance remains separate.

The historical task helper remains for its tests; new installations exclusively
use SCM, not scheduled boot tasks. The manual workflow
`.github/workflows/windows-installer-services.yml` prepares real registration,
virtual-account negative-access checks, idempotence and repair/restart on a
disposable hosted runner. It has not been dispatched and is not evidence of a
passing service installation. The current developer token is not elevated.
