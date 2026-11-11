# ADR 0046: native installer distribution and scoped maintenance

Status: accepted for implementation, 2026-11-11. Full product delivery remains
tracked in `docs/installer-requirements.md`.

## Decision

Keep the existing local Python orchestrator and Core authority. Build standalone
terminal executables on each target OS/architecture with PyInstaller. PyInstaller
is a build dependency only, required because a manually installed Python runtime
is not an acceptable end-user prerequisite. Bundle only explicit installer assets;
do not package the repository, private data, keys or arbitrary local config.
Preserve the headless terminal entrypoint. Browser UI work shares this lifecycle,
not an independently privileged website service.

Image signatures and executable signatures are separate. Unsigned developer
outputs must never become public downloads automatically. Website metadata is
generated from actual published assets; an empty catalog renders availability
information and help without invented or disabled download links.

Extend the same installer with a scoped consistent backup/restore lifecycle.
Core is the authoritative writer: stop the owned Core service for the bounded
database-plus-Knowledge capture, restart it in a finally path, and retain exact
release/image/schema/credential metadata. Reuse GnuPG authenticated symmetric
encryption already used by the repository's recovery drill, with passphrase on
stdin and an isolated keyring. Never promote decryption output before successful
integrity validation. Never archive the live PostgreSQL data directory.

Restoration must first verify all archive paths, digests, compatibility and original
keys in a disposable marked, unpublished target. A backup file being present is
not successful restore evidence. Repair never regenerates an existing credential
key. Destructive removal must separately confirm software and installation data;
foreign Ollama/runtime resources remain outside that scope.

## Platform findings

Windows Docker Desktop/WSL state is not treated as a system boot service. Linux
containers require a Linux kernel/runtime. Native packaging does not by itself
implement Windows provisioning. A suitable Windows runtime/service path must be
implemented and tested before that requirement changes state. No compatibility
claim follows solely from a frozen Windows executable.

Official references checked on 2026-11-11:

* [PyInstaller target-specific builds](https://pyinstaller.org/en/stable/usage.html)
  and [asset paths in frozen applications](https://pyinstaller.org/en/stable/runtime-information.html).
* [Microsoft Linux containers on Windows](https://learn.microsoft.com/en-us/virtualization/windowscontainers/deploy-containers/set-up-linux-containers).
* [Docker Windows permissions/service requirements](https://docs.docker.com/desktop/setup/install/windows-permission-requirements/).
* [Hyper-V automatic start configuration](https://learn.microsoft.com/en-us/powershell/module/hyper-v/set-vm?view=windowsserver2025-ps)
  is a possible VM-based alternative, not an implemented Kyrion backend.
* [Ollama Windows](https://docs.ollama.com/windows) describes native runtime paths;
  service management still requires explicit Kyrion lifecycle implementation.
