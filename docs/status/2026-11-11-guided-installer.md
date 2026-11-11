# Guided installer source verification, 2026-11-11

Work remains on `master`. This is an incremental source delivery, **not completion
of the full installer product request**. No commit, productive deployment, public
release, physical device command, provider login or paid request was performed.
See [inventory, continuing plan and support matrix](../guided-installer.md) and
[operator/build instructions](../../infrastructure/installer-v1/README.md).

## Actual local results

| Check | Result |
| --- | --- |
| Python unittest discovery | 42 tests run, 40 passed, 2 skipped |
| Real Ed25519 signature and tampered-manifest rejection | Passed with temporary fixture keys using installed Git OpenSSL |
| Real local TLS certificate generation and SAN inspection | Passed in temporary storage; ownership calls mocked on Windows |
| Actual curl config/stdin request to isolated loopback HTTP fixture | Passed, including quoted password and bearer header preservation |
| Injected Compose fresh/failure orchestration | Passed; never contacts a Docker daemon or creates real accounts/devices |
| Journal preservation/resume/change refusal and locale parity | Passed |
| Ruff 0.16.1 lint and format check | Passed for 12 new/reworked Python modules/test files; legacy configure/test file not included in Ruff scope |
| Python module compilation | Passed |
| Shell syntax through installed Git Bash | Passed for installer/release entrypoints |
| PowerShell entrypoint parser | No syntax errors |
| CI YAML parse | Passed, including Linux/Windows installer matrix |
| Docker Compose config validation | Passed without starting any service |
| Allowlisted Python archive build and executable probe | Passed; archive requires Python 3.12+ and is unsigned |
| Actual Windows x64 target inventory | Passed, correctly reports no provisioning path or platform acceptance |
| git diff whitespace check | Passed |

Skipped: real POSIX `fcntl` concurrent lock test (this host is Windows), and a
fixture symlink test (host policy denies creation). Linux CI is configured to run
these, but no hosted CI run was started here. Signature tests use synthetic keys;
they do not establish productive signing-key custody or trust distribution.

Generated local artifact: `build/kyrion-installer-20261111.pyz` (ignored build
output). The packager emits a SHA-256 as an integrity aid; it does not sign the
installer. Run `python build/kyrion-installer-20261111.pyz --probe` for read-only
use. Do not publish it as an accepted Windows/Linux installer.

## Unperformed acceptance

No fresh Debian/Raspberry Pi OS host was installed, no actual image loading or
Core/Web image build was performed, and no cold boot, standby/reconnection,
offline owner login, central identity linking, HA connection/import, backup/restore
or updater acceptance was run against real services. WSL distribution enumeration
was unavailable to this sandbox; it was not bypassed. The Core Dockerfile now
installs curl required by its existing healthcheck, but that resulting image
still requires a real builder/host rehearsal.

Candidate source targets are Debian 13 x64/ARM64 and Raspberry Pi OS 13 ARM64.
Windows x64 has inventory only. No platform was newly accepted or released.
Core owns all authentication, membership and integration operations; their existing
service tests are not replaced by installer transport fixtures. Full application
and physical acceptance must be recorded separately.

## Remaining implementation, separate from external prerequisites

Native Windows service/runtime provisioning, multi-device pairing/task transfer,
existing remote Space selection, recovery provisioning, HA selective import and
control, signed model catalog/Ollama lifecycle, Velora provisioning, update service,
encrypted portable backups/restore, repair/uninstall, interactive action tutorial,
QR summary, website download/help/advice pages and authenticated package/key
rotation remain source work. The [continuing plan](../guided-installer.md) tracks
these explicitly. Productive identity configuration, signing-key custody, release
licensing/trust distribution and disposable OS/hardware acceptance are separate
external prerequisites. They do not excuse the unimplemented source stages.
