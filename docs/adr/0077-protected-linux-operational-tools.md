# ADR 0077: Protect Linux installation and recovery executable boundaries

Status: Accepted for implementation, 2026-11-14.

Extend the OS-owned tool resolver from ADR 0076 to mutating Linux operations.
Docker, OpenSSL and GnuPG are selected from fixed protected system locations,
not caller PATH aliases. Default child environments do not inherit loader hooks,
proxy/provider credentials or arbitrary runtime overrides. Existing approved
Compose environment files and explicit stdin/file streams remain the operation's
configuration/data boundary; this is not another deployment backend.

Linux encryption/decryption verifies the fixed GnuPG suite before passing a
password. Explicit unsupported executables cannot bypass that verification.
Plaintext scratch uses a protected parent; the GnuPG agent uses a short private
directory below checked sticky system /tmp, avoiding UNIX-socket path overflow.
Default Linux restore scratch also ignores caller TMPDIR.
Windows native agent scratch uses a short exclusive private directory under the
OS-resolved ProgramFiles known folder, verified through the existing ancestor and
administrator policy (ADR 0078). Long/unsafe locations fail before password handoff. A real
portable GnuPG probe also exposed the socket-length limit on Windows; a successful
DLL/version probe alone is insufficient.

[SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
and the [ProgramFiles identifier](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)
were checked against official documentation on 2026-11-14.
Windows native recovery continues to use its independently verified portable
payload and protected environment. The unfrozen Windows developer GnuPG path
remains a clearly separate test/operator mechanism; frozen builds cannot silently
fall back to user PATH GnuPG.

Keep domain authorization, authority/update/restore fences, confirmations and
existing recovery formats unchanged. Missing tools fail explicitly and do not
trigger automatic OS mutation. Verify actual encryption and Core/database restore
again; mocks alone do not establish operational compatibility.
