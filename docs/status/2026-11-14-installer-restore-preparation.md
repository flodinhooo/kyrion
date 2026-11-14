# Fresh restore target acquisition and prerequisite preparation

The overall assignment remains open; no partial user acceptance is requested.
ADR 0074 extends the existing guided restore, authority fence, signed acquisition
and package journal rather than creating another recovery implementation.

The downloaded installer now runs read-only platform/resource preflight before
automatically obtaining a compatible signed runtime bundle for restore when no
manual trust key was supplied. Download and restore/OS mutation have separate
consent. Native Windows reuses portable service/runtime provisioning. Debian 13
uses the reviewed Docker/Compose/GnuPG prerequisite operation before application
runtime provisioning. A changed backup after review stops preparation.

The early private Linux journal is bound to the exact backup hash and marked
prepared-for-restore **before** APT mutation. Package and Docker-service operations
cross that fence only with an explicit identical request. Changed/malformed
requests, ordinary install, ordinary crypto maintenance, retired authority and
unfinished updates remain blocked. Successful prerequisite setup does not clear
the restore fence or claim application activation. Repetition resumes the same
manifest/configuration/request and package plan. The existing source-retirement
receipt and Core-owned restore disposition still govern activation.

## Verification

- Full installer suites: 410 tests on Windows (three intentional skips), 412 on
  isolated Debian (sixteen intentional skips); Ruff and formatting pass.
- Guided boundary tests inject OS/download/data mutation, stop at the existing
  real restore entrypoint and assert exact authority/hash propagation, cancellation,
  early preflight failure and changed-backup refusal. Real private journal tests
  verify request/fence persistence and matching replay; they are not OS acceptance.
- Actual new Debian 13 chroot package installation under the matching restore
  fence, Docker/Compose/GnuPG probes, vendor unit integrity, repeat and retained
  activation fence passed. No daemon was started. Evidence:
  `build/isolated-linux/runtime-packages-report.json`, owned root
  `/work/crypto-clean-fixtures/a17b49e7bcb2420a9dd056e4c36c6d34`.
- Actual Core/PostgreSQL 17/GnuPG application restore passed again:
  `build/isolated-linux/application-restore-report.json`. The test covers interrupted
  import/replay, original keys/data/roles, source retirement, revoked old sessions,
  offline login after process restart, recovery-key binding, tamper rejection and
  transactional rollback. Seeded linked identity is synthetic. Service lifecycle
  uses explicit process adapters in an isolated network namespace, not SCM/Docker
  or cold-boot acceptance. No household device was addressed.

Native developer builds `.20261114.10` are recorded in `build/native-installer/`
with adjacent digest/raw-source metadata. They remain unsigned/unpublished with
no productive release channel and `platformInstallationAccepted: false`.
Both exact package source snapshots and artifact hashes were checked. Windows
EXE: 12,726,442 bytes, SHA-256
`a19a798a7728f3793270e8eeaff58c71f4685becbf9e6f4d2c45a1dd87b365f6`.
Linux AMD64 archive: 14,532,542 bytes, SHA-256
`eff48a24e5a42b5f2d473cd7c85c596a73c74692dfc7e122a43ed8b4b39ac0b7`.

## Remaining limits

The automatic selector still accepts schema 49/API 1. This does not implement
unknown-source recovery, legacy unfenced-source activation or same-root disaster
replacement. OS-runtime repair, distributed coordination, full AI/voice/tutorial
and local Web administration remain source work in the requirements matrix.
Actual clean-host application/systemd restart, Windows service startup before
login, physical ARM64/audio/radio and productive signing/publication are separate
acceptance boundaries. This checkpoint does not declare overall test readiness.
