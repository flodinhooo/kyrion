# Database restart and systemd rate-limit corrections

This continues the [Debian Compose evidence](2026-11-14-installer-debian-compose.md).
The [full requirement ledger](../installer-requirements.md) remains binding and
open. No partial user acceptance is requested.

## Implementation

The first database restart failure is now captured. Debian Compose 2.26.1-4
reports the stopped PostgreSQL container as running, then waiting fails with
`exited (0)`. Independent daemon inspection proves the old cleanly exited
process and stale unhealthy health record. This supersedes the uncaptured-error
limitation; an upstream root-cause claim is not made.

The update adapter starts only PostgreSQL with local-only image policy and checks
actual daemon state within a finite deadline/attempt limit. Before accepting
health or starting a cleanly exited container, it checks installation project,
service label, pinned image and exact bind data directory. That container may
receive one explicit start. Further exits, OOM, fatal exit or an unhealthy running
process fail closed. Writers remain fenced. There is no generic retry of
migrations or data replacement. Errors have stable codes and DE/EN guidance.

A real repeat transaction then exposed `start-limit-hit`: the generated
`StartLimitIntervalSec=infinity` counted all starts over the unit lifetime,
including successful manual starts. The [systemd documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html#StartLimitIntervalSec=interval)
defines that behavior. The supervisor now allows three starts per five minutes.
Reviewed administrator reconfiguration resets an actually failed unit; the
background worker never resets its budget. An initial draft reset new unloaded
units unconditionally and failed native first registration. The correction first
checks actual failed state. Build `.21` is not accepted as a fresh installation.

## Verification

- Five injected-Docker regressions cover stale clean exit, starting/healthy state,
  a second exit without restart loops, foreign identity/image/data mounts,
  OOM/fatal state and bounded timeout. These are unit tests, not OS acceptance.
- Complete suites pass: 476 Windows tests (nine skips), 484 isolated Linux tests
  (twenty skips). A restricted Windows run failed SDK/ACL/GPG prerequisites; the
  correctly provisioned developer invocation passes. No Windows SCM acceptance
  is implied. Full installer Ruff and changed-file format/whitespace checks pass.
- The real restart reproducer passes, observing one actual start and daemon
  health transition. The repeat transaction reaches schema 50 and its systemd
  fence. After correcting the rate-limit registration, actual recovery restores
  schema 49, identity, original knowledge and local login.
- The fresh complete-stack run with native `.22` passes without an unplanned
  retry: fresh/repeated installation, native registration, real systemd startup,
  TLS health, encrypted backup, migration, deliberately interrupted activation,
  real startup fence, resumed activation and recovery with preserved identity.
  Eligibility, systemd and readiness probes are not injected. Evidence:
  `build/isolated-linux/systemd-stack-run.txt` and `systemd-stack-report.json`.
  Automatic application-backup testing remains a separate next check.
- Native development `.20261114.22` packages pass executable/resource smoke and
  exact source/artifact hash checks. Windows EXE: 12,770,857 bytes, SHA-256
  `54a9d64759083184442c817236f970549b7d954fe9ecfd1664a5bdcfbdb616d7`.
  Linux AMD64 archive: 14,579,269 bytes, SHA-256
  `b81a882f4f0709b9793007af3ce349c8b5f68b163fba2cb932beeb082d18f4a7`.
  Both remain unsigned, unpublished and `platformInstallationAccepted: false`.

Evidence: `build/isolated-linux/systemd-source-restart-reproduction.txt`,
`systemd-post-limit-recovery.txt`, `test-report-current.txt`, and
`build/installer-tests-20261114-database-health-final.txt`. Raw failure logs stay
private inside the marked guest. Synthetic releases and fixture namespace
drop-ins do not establish productive release, browser SSO, physical cold boot,
ARM64 or Windows pre-login acceptance.
