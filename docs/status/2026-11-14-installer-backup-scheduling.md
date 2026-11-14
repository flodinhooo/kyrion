# Installer continuation: installed encrypted backup scheduling

The complete installer assignment remains open. No partial user acceptance is
requested. This work reuses existing capture, GnuPG, journal and owned scheduler
primitives; it introduces no account/Space store or second archive format.

## Implemented behavior

`backup_policy.py`, `backup_store.py`, `backup_schedule.py` and `backup_worker.py`
provide explicit UTC consent, protected installation-bound stores, separate key
export, atomic no-overwrite publication, actual scheduler status, persistent
capture/verification checkpoints, three-attempt continuation and hash-checked
retention. Changing stores retains their separate receipts. A missing registered
marker is refused, not recreated. Known keys are not silently adopted after
change. Original maintenance keys are shared with automatic updates, protected
from Core and excluded from backups; update setup also uses atomic publication
and refuses an export alongside known backup stores.

Scheduled archive metadata is authenticated and bound to the exact run UUID,
installation and configuration. A replayed compatible old archive is rejected.
Pending service restoration runs before policy/window/storage checks, after authority and update fences. Three durable automatic attempts prevent restart loops; an explicit manual attempt can retry after exhaustion. Native recovery checks every owned service before starting only previously running roles. These regressions inject SCM/Compose boundaries and do not constitute OS lifecycle acceptance.

Both native and Compose capture receive that binding before runtime/service
access. Verification is not application-restore acceptance. Existing actual
Core/PostgreSQL/GPG restore evidence remains separate.

The guided terminal offers configuration after setup/restore and maintenance
supports configure/status/run-now/disable/reset-incomplete. English and German
are paired. System changes, quiescence, key custody and retention are reviewed.
Removal/retirement clean only the owned schedule, leaving external backups and
exports. Linux GnuPG package bootstrap is still an open runtime prerequisite
implementation; absence is detected before backup scheduling is enabled.

## Evidence and boundaries

Full suites pass: **356 Windows tests (three skips)** and **358 isolated Linux
tests (16 skips)**. Ruff lint passes. A whole-directory formatter check identifies nine pre-existing files; changed modules are formatted. Added regressions use real journals and files;
OS ownership, frozen execution and scheduling boundaries are explicitly injected
where documented. Actual GnuPG/archive verification rejects replayed data. The
Windows Task Scheduler COM parser validates the actual SYSTEM definition and
rejects modified actions without registering a task on the developer host.

Actual owned Debian 13 systemd evidence:
`build/isolated-linux/backup-definitions-20261114-4.json` validates backup/update/
startup unit definitions through `systemd-analyze verify`.
`build/isolated-linux/backup-timer-20261114-4.json` records a real registered
timer's default boot trigger invoking the frozen worker, durable update-fence
deferral, and real protected store/key ownership. The journal is synthetic and
no application capture is executed. This is not physical cold boot or Windows
pre-login acceptance. Exact worker SHA-256:
`d52d0420dd60b5610070aae36d125ada945a0b00d93a5c131a5072bf5aa519e4`.
The current `.20261114.4` worker includes authenticated run-ID binding and bounded
pending-service recovery. Its Linux archive is `build/native-installer/kyrion-installer-0.0.0-dev.20261114.4-linux-amd64.tar.gz`; the native build/smoke metadata is adjacent.

Windows standalone `.20261114.3` builds and actually reports backup protocol 1;
its exact source hashes were checked at build time. A real non-elevated probe
rejects the unprepared target with `E_NATIVE_ELEVATION`, creating nothing and
registering no task. Report: `build/native-backup-protocol-report.json`.
Current Windows standalone `.20261114.4` was rebuilt, smoke-tested and passed the same raw-source-hash/protocol/elevation checks. SHA-256: `b040d4e974c27a7570cad6af91e4cb1a80979c8e83c83d0039817f88d9e4a33b`. No release is published.

The hosted Windows-only service fixture now prepares real SYSTEM backup-task
capture/verification on its fresh synthetic installation. It manually triggers
that task and explicitly does not call that boot acceptance. The manual Linux CI
adds the actual backup-timer fixture. Neither workflow has been dispatched.

Complete application capture through the installed scheduler, full native SCM
acceptance, physical restart/standby, distributed coordination and remaining
product journeys remain separately required. The full Linux stack test still
has an OCI/runtime/environment failure; the Docker client also exhibited actual
`wait_on_page_bit_common` disk sleep even for `--version`. The separate Docker
Desktop endpoint is unavailable. These failures are not reported as successes
and do not substitute for missing source implementations elsewhere in the matrix.
