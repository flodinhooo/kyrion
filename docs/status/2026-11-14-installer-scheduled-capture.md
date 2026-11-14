# Installed automatic application capture

The full [installer requirement ledger](../installer-requirements.md) remains open.
This is developer evidence, not a partial user-test request or release approval.

## Correction and resulting behavior

The first real installed-timer capture produced a valid encrypted archive but
its immediate post-capture Core health check failed. The old Linux backup path
cleared the durable service obligation after `compose start`, before application
readiness was established. A successful start request alone is insufficient.

Capture and recovery now share the existing owned service-restoration function.
It validates the local daemon, installation/service identity, pinned image and
exact knowledge bind, then waits for current Core container health using the
same bounded daemon checks as PostgreSQL startup. A clean stopped container may
be started once; failing services are not restarted in an unlimited loop.
Only proven Core health clears `backupServiceRecovery`. Failure preserves that
obligation and the existing bounded automatic recovery attempts. The shared
function also checks authority/update fences before any runtime operation.
It does not start other services that were intentionally offline.

## Actual and automated evidence

- Complete suites: **480 Windows tests (nine skips)** and **488 isolated Linux
  tests (twenty skips)** pass. Full installer lint and changed-file formatting
  pass. New regressions prove the obligation survives failed Core health,
  rejects foreign knowledge mounts, rejects arbitrary service names and cannot
  bypass a migration fence. Docker/OS interactions are injected in unit tests.
- `tests/integration/verify-installed-backup.py` runs on the completed, marked
  disposable Debian/systemd fixture with native worker `.20261114.24`.
  The real native CLI configures startup and the approved daily backup window,
  protected local store and separate recovery-key export. Existing backups and
  keys are preserved on repeat developer runs.
- The actual systemd timer invokes the frozen automatic worker. Actual
  Core/PostgreSQL capture, GnuPG encryption, archive authentication and expected
  knowledge bytes are verified. Core/TLS application health and the same local
  account identity are checked afterward. A second real service invocation in
  the same slot confirms no duplicate capture or history entry. No service,
  cryptographic, health or timer probe is injected; namespace drop-ins are
  explicitly fixture-specific.
- Evidence: `build/isolated-linux/installed-backup-run.txt` and the guest's
  `installed-backup-report.json`; regression logs are
  `build/installer-tests-20261114-backup-health-final.txt` and
  `build/isolated-linux/test-report-current.txt`. The first failed capture test
  is not accepted; its archive remains preserved. The later corrected run passes.
- Native development `.20261114.24` packages pass executable/resource smoke and
  exact current-source/artifact hashes. Windows EXE: 12,772,635 bytes, SHA-256
  `7e03a4b72190d8b8f25a7b94b7f8f6d70bbf80a419e08ee851e77e1b3c32b904`.
  Linux AMD64 archive: 14,578,431 bytes, SHA-256
  `f2fcb8bb15360b67e08497d4c39ea16b4e5a10a8a1b5ff2ec3e8f9a24d2af8f5`.
  Both are unsigned, unpublished and `platformInstallationAccepted: false`.

This proves installed scheduled capture and restored application availability,
not portable database import, physical cold boot or privileged Windows task/SCM
acceptance. Actual portable import/application restore has separate evidence in
the existing native-backup-verification and transaction reports. Full product
journeys, distributed nodes, managed AI/voice and local administration gaps stay
source work. The next available platform check is owned Linux guest init restart;
that must also remain distinct from physical Linux or Windows pre-login boot.
