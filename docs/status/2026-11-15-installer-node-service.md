# Linux prepared-node boot-service checkpoint

The full installer assignment remains open. This is developer evidence, not a
partial user handoff. ADR 0086 records the deployment boundary.

## Resulting behavior

The downloaded native Linux installer now supports reviewed `--node-service
install|repair|status|disable|remove`. It uses the existing installer journal,
exclusive target lock, frozen-worker integrity and host binding. Core maintains
the same device, Space, enrollment and task authority. A dedicated non-login
technical Linux account runs enrollment and the service; no additional Kyrion
human identity is created. Credentials remain private to that account. The
service uses systemd's system manager and multi-user boot target, independently
of desktop login, with bounded restarts and control-group termination.

The worker has no capabilities and cannot directly access USB/audio hardware.
Only its private agent directory is writable; system/home paths are protected.
This initial service profile supports existing network integration transport.
Core-granted tasks do not install missing hardware runtimes or enable a mic.

Account creation, worker publication and service registration are journaled.
Repeat with the same reviewed enrollment inputs preserves the node identity;
conflicting inputs fail before retargeting. Pending enrollment can resume from
its protected existing intent. Foreign/changed worker and unit definitions are
preserved and rejected. Core database/Compose maintenance explicitly refuses a
node journal. Removing the service preserves the technical account, credentials
and worker for repair; it is not complete node software/data deletion or Core
device revocation. `--devices` provides the separate authorized Core removal.

Status separates registration, enablement, process activity and fresh acknowledged
Core connectivity. The latter requires a current service-owned process and a
bounded suspend-aware observation. Missing/stale evidence stays unknown.

## Verification

`tests/integration/verify-node-service.py` ran the actual native installer and
copied worker, actual dedicated UID, actual PID-1 systemd, Core schema 51,
PostgreSQL and verified TLS in the owned Debian 13 AMD64 WSL developer distro.
It passed enrollment, same-input repeat, conflicting-code refusal, service
restart, Core outage/reconnection, disable, repair and service removal, while
preserving the credentials and a single Core identity. No successful operating
system/Core response was injected. No household command, microphone activation,
productive installation or release publication occurred.

The fixture binds Core and PostgreSQL only to loopback. Unlike the separate
foreground proxy fixture, this system-manager test uses the development distro's
actual network namespace, not an additional per-process namespace. Test data and
technical accounts remain inside the disposable owned distro. The manual Linux
CI workflow now contains the same check; hosted execution was not triggered.

The initial actual check found that `reset-failed` rejects an unloaded fresh unit.
The installer now validates the loaded fragment/drop-ins first and resets only
an actual failed state. A regression test covers both inactive and failed units.
The fixture also publishes its private control requests with final UID before
atomic visibility, preventing a test-only permission race.

Reported developer suites: Windows installer 512 tests, ten skips; Linux
installer 521 tests, twenty skips; shared agent 56 passed/sixteen Windows skips
and 72 Linux passed. Ruff and changed-file formatting pass. The final review-only
probe correction additionally passes the targeted node-service suite and actual
native installation fixture; it avoids presenting central Docker requirements
as node-service prerequisites. Core's unchanged security/gateway checkpoint has
218 tests, zero failures/errors and one skip.

The current Core JAR `998ddd7a7e88d99a052ada709882fcf83f3e6022aec149749c45ad1853057f00`
also passed actual encrypted backup, inactive verification, interrupted restore,
offline identity recovery and old gateway/voice credential revocation. Its actual
Flyway update fixture passed interrupted activation and database snapshot recovery,
including a deliberately failing migration. The target schema 52 in that test is
a controlled synthetic sentinel, not released/supported schema 52. These fixtures
use process lifecycle adapters and do not establish SCM/Docker or cold-boot
acceptance. Private reports: `application-restore-schema51-report.json` and
`update-transaction-schema51-report.json` under `build/isolated-linux`.

| Private artifact 0.0.0-dev.20261115.9 | Bytes | SHA-256 |
| --- | ---: | --- |
| Windows AMD64 | 12,859,745 | `a1d026d379b7a4d60c24499a66ffbeccd7253c38b648ece8a724626731e8461c` |
| Linux AMD64 | 14,667,332 | `287054a73cccc51dd1930585b05c34517912c68dfc53b15ac4291d41f603454b` |

Both native builds pass embedded version/channel/CA smoke and match checkpoint
sources. They are unsigned and unpublished. Windows compilation does not imply a
Windows prepared-node service implementation. Physical cold boot, kernel reboot,
ARM64 and Windows SCM acceptance remain unverified. The actual isolated system
service/start/restart result is distinct from these external acceptance limits.

## Remaining source work

Owner-facing pairing export/import, existing-proxy extension, full guided task
placement, Windows prepared-node storage/service, exclusive handoff, node
backup/update/data deletion and full local management UI remain open. R23-R29
are not declared complete. Subsequent work starts with the owner-side authorized
pairing path and continues through the binding requirements ledger.
