# ADR 0056: Native operational backup runtime

Status: accepted for implementation, 2026-11-13. Full restore/identity fencing
and installed backup scheduling remain separately tracked source work.

Preserve ADR0046's existing GnuPG authenticated backup format and archive
validation. Do not introduce a second account/Space store, replace personal
backups, design another encryption envelope, or require a customer Git/Python
installation. Operational backups contain original server keys and belong to
privileged installation maintenance; personal backups continue to exclude them.

The native installer support payload may include a reviewed portable GnuPG
dependency under `runtime/installer/gnupg`, already within the signed native
manifest's installer-component namespace. Its individual executables/libraries,
portable marker, vendor version/provenance and original legal notices are covered
by the existing file hashes/signature. This is an installer support dependency,
not another running Kyrion service. Keep development artifacts unpublished until
all release/license gates pass.

Use the official Windows distribution only after pinned-size/SHA-256 validation
and upstream detached-signature verification against reviewed release-key
fingerprints. A build-only archive extractor may prepare the portable public
tree; never execute the vendor system installer. Do not copy its NSIS plugins,
uninstaller or user keyring/cache. Record exact extracted-file hashes.

At runtime select the managed absolute GnuPG executable, never a caller's PATH
alias. Use a private per-operation homedir, passphrase through stdin, no captured
secret output and the matching absolute gpgconf to terminate only that homedir's
agent. Do not change registry setup, global GnuPG configuration or foreign agent
processes. A snapshot still requires a successful archive integrity check; an
encrypted file alone is not restore acceptance.

Native capture will reuse the same archive manifest/inspection and original-key
coverage as Linux. Validate owned services before a bounded Core/Web pause, keep
PostgreSQL available for a consistent logical dump, and restore the previous
service state in a finally path. Never copy the live database directory. Full
restore must separately verify compatibility, identity disposition and activation
in an isolated target; this runtime dependency does not provide those policies.

Official references reviewed on 2026-11-13:

- [GnuPG downloads](https://www.gnupg.org/download/index.html) provides the current
  simple Windows distribution and detached signature.
- [Official release keys](https://www.gnupg.org/signature_key.html) identifies the
  upstream release trust anchors. The inspected 2.5.24 Windows package verifies
  against `6DAA6E64A76D2840571B4902528897B826403ADA`.
- [gpgconf portable operation](https://gnupg.org/documentation/manuals/gnupg26/gpgconf.1.html)
  documents the Windows portable marker and explicit homedir behavior.

Developer inspection found actual AMD64 binaries despite the historical `w32`
archive name. The extracted portable tool passes synthetic encryption/decryption,
wrong-password rejection and both-way interoperability with the existing recovery
format. Those tests do not constitute native backup capture/restore acceptance.
