# ADR 0090: Windows storage for the existing prepared agent

Status: Accepted for implementation

## Decision

Extend the existing gateway agent's prepared enrollment, pending acknowledgement,
AgentConfig and runtime lock; do not create another identity or credential store.
The downloaded installer continues to embed explicitly allowlisted agent source.
Legacy deployed Linux configuration and enrollment remain unchanged.

Windows prepared storage initially supports local fixed NTFS volumes. Refuse
UNC/device paths, alternate data streams, ambiguous/reserved names, reparse
components, foreign owners, hard-linked credential files and untrusted writable
ancestors. Existing files/ACLs must never be silently repaired or adopted.

Use typed Win32 APIs without PowerShell, a compiler or another runtime dependency.
New private directories/files receive a protected DACL at creation, with the
current process identity, System and local Administrators as trusted principals.
The current identity owns managed agent secrets. Ancestor validation additionally
recognizes the resolved local TrustedInstaller identity, matching the existing
installer's trust boundary. Inspect the actual descriptor rather than interpreting
POSIX mode bits as Windows security.

Publish already flushed private temporary files with a same-directory move that
refuses an existing destination. Lock files use exclusive native handles, released
by the OS on process death; never remove a live lock to manufacture availability.
Prepared Linux publication uses `renameat2(RENAME_NOREPLACE)` on the supported
modern Linux/glibc path rather than a temporary hard link. A process killed
between link creation and cleanup must not leave an otherwise committed secret
with two links that private-file validation cannot accept. Missing API/filesystem
support is a refusal, not an overwrite fallback. Legacy non-prepared saves remain
unchanged. Test an actual abruptly terminated publisher, not just an exception
whose `finally` block still runs.
Input transfer files can use an already private inherited descriptor, but managed
credentials require the protected owner-bound descriptor. Imported credentials
are not decrypted or copied from another identity's existing agent profile.

Windows service installation must reuse the existing installer journal, SCM host
and virtual-service identity design. A frozen one-file console executable is not
silently presented as the installed service-host distribution: use the existing
one-directory host, immutable source/version inventory and authenticated release
distribution boundary. That packaging/service work is separate from implementing
private storage and must be finished before claiming complete Windows nodes.

Do not enable Linux-specific hardware probes on Windows. Add actual supported
Windows inventory and an explicit unknown-value contract through Core and local
presentation before accepting Windows heartbeats/runtime. Retain the short task
permission lease and fail-closed behavior. Use a suspend-aware Windows timer;
do not imply exclusive cross-device ownership from a local file lock.

## Verification

Test actual native descriptors, private publication/no overwrite, corrupted or
foreign ACL refusal, reparse/hard-link refusal, cross-process lock contention and
lock release. Exercise actual Core/TLS enrollment and lost acknowledgement from a
fixed source/native artifact. Label protocol doubles separately. SCM/virtual-user,
standby and pre-login acceptance require a disposable elevated system and are not
established by user-file or process fixtures.

Official references checked before implementation:
[CreateFile sharing](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[MoveFileEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw),
[file security descriptors](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getfilesecurityw),
[DACL access](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptordacl),
and [suspend-aware Windows elapsed time](https://learn.microsoft.com/en-us/windows/win32/sysinfo/windows-time).
Linux reference: [renameat2 no-replace semantics](https://man7.org/linux/man-pages/man2/rename.2.html).
