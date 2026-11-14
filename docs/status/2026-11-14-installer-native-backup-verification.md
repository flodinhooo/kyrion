# Inactive native backup database verification

The full installer assignment remains open. ADR 0079 adds the missing installed
Windows `--verify-backup` path to existing maintenance, with bilingual review and
errors. A signed/verified installed Core payload supplies a migration-only
entrypoint. PostgreSQL tools, Java, GnuPG, cluster location and major version are
verified before the temporary database operation. Older Core payloads without
the entrypoint are refused rather than silently using PATH tools or Docker.

After decrypting and validating the archive, a random database is created from
template0. Packaged Core migrations create its schema without Spring application
services. Existing portable binary-row import checks the descriptor, restores
rows/sequences, validates foreign keys and compares recorded counts. Archived
SQL is never executed. Only this completed operation produces a verification
receipt; normal backup capture still reports `restoreVerified: false`.

The live application database is never selected for replacement. No integration,
HTTP application server, scheduler or device action runs in the verification
database. The installation lock and authority fences remain enforced. A private
journal records the random name and acknowledged database OID. Exact identity
permits cleanup/resumption; replaced or unacknowledged databases are preserved
for administrator review. Database deletion is not secure erasure of normal WAL.
Native capture also checks the short protected GnuPG parent before scratch
creation or writer pauses. Existing lossy German runtime translations were fixed.

## Developer evidence

- Complete installer suite: Windows 448 tests, eight skips; isolated Debian 13
  455 tests, twenty skips. Changed-file format and installer-wide Ruff lint pass.
  Both installer CI workflow shapes/YAML are valid.
- Core builds offline with Java 21. Across configured security runs, 195 tests
  have zero failures/errors and one existing skip. Initial sandboxed runs lacked
  Docker/temp-file access; the first unrestricted run also lacked the eight
  migration rehearsals' mandatory artifact configuration. Those eight pass when
  supplied the immutable reviewed JAR and Python path. Combined suite ledger:
  `build/core-security-native-verification-report.json`; raw configured rerun:
  `build/core-backup-verification-rehearsal-configured.txt`. This is split-run
  evidence, not a fabricated single green invocation.
- Actual Core/PostgreSQL/GnuPG integration passes on Windows and isolated Linux:
  empty-schema migration, encrypted archive validation, binary imports/counts,
  wrong password, injected post-schema failure cleanup, acknowledged leftover
  cleanup and no live database/Core-start mutation. The subsequent complete
  source-fenced restore, role/link preservation, interrupted import, audit
  tamper/rollback, offline process restart and credential disposition also pass.
  Windows uses authenticated/hash-checked portable Java/PostgreSQL binaries,
  synthetic user-protected directories and a process adapter. It does not test
  actual native service identities or the native cluster-selection constructor.
  Linux uses its owned network namespace and unprivileged fixture user.
  Evidence: `build/native-backup-windows-process-run.txt`,
  `build/native-verification-process-764030c263974f7eba15f959ffe92a0a/report.json`,
  `build/isolated-linux/application-restore-report.json`.
- The full actual Linux update transaction passes again with the new Core:
  backup, real migration and failing migration, interruptions, recovery and
  host/account/Space identity preservation. Its process adapter does not certify
  Docker, SCM or cold boot: `build/isolated-linux/update-transaction-report.json`.
- Core JAR SHA-256 for these current integration runs:
  `9ba3c97a81cc5926b0adff0d2d1fa8c3c07cd4897e015635426e400773caa048`.
- Native development `.20261114.16` packages pass smoke/resource checks and exact
  raw-source/artifact hashing. Windows EXE: 12,758,609 bytes, SHA-256
  `c1d91b796eeb758a3725139ff2729617d75621ee6c7a6d3c849d75971f33824b`.
  Linux AMD64 archive: 14,564,004 bytes, SHA-256
  `6d99077d07365cebc17463fe1b404bacd7bc324f07f526674a55677431d25044`.
  Artifacts/metadata are in `build/native-installer/`, unsigned, unpublished and
  explicitly `platformInstallationAccepted: false`.

Actual elevated SCM/ACL verification is prepared in the Windows CI service test,
not executed locally. Whole-host boot, ARM64 and physical hardware acceptance
remain separate. Bare-target verification, same-root disaster restore,
unknown-source activation, distributed operation, managed AI/Voice, the local
browser wizard and other matrix gaps remain source work. No user partial test or
overall acceptance is requested.
