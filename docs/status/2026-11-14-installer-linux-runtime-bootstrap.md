# Guided Linux runtime prerequisites, 2026-11-14

This continues the full installer assignment. It is not a user acceptance handoff.
ADR 0072 records the early-journal and package/service boundaries.

## Source behavior

`linux_packages.py` contains the shared consented APT operation extracted from
the tested GnuPG path. `linux_crypto.py` retains its compatible entrypoints and
existing journal format. `linux_runtime.py` adds the real Debian 13 package
selection (`docker.io`, the separately packaged `docker-cli`, Compose v2,
GnuPG and CA certificates), tool probes and system-service preparation.
Metadata-only intents can close without inventing a package receipt when tools
were supplied elsewhere. Active owned package transactions cannot overlap.

The downloaded guided flow performs actual target/resource checks before large
downloads. After INSTALL it authenticates the release again, creates/resumes the
same protected `reviewed` journal and obtains service consent before APT, because
package maintainer scripts can start/enable Docker. Exact package review remains
separate. A reviewed journal still receives fresh port/container checks; an
unowned directory or malformed progress never weakens that policy.

Missing CLI plus unknown daemon data/configuration is refused. A recorded own
in-progress installation can resume when maintainer scripts created daemon data
before its CLI became available. Existing custom executable/context/environment
and stopped modified/masked units are preserved. Healthy prepared local services
can be reused. No daemon configuration, Docker group membership or TCP API is
created, and shared runtimes are retained on Kyrion removal.

Service enable/start is checkpointed, with ownership/vendor-file checks before
mutation. Real rootful local daemon/socket validation reuses the existing Compose
adapter. Actual Compose/systemd/network probes must pass before the runtime is
reported running. Configured startup is distinct from physical cold boot.
Known documentation omissions in minimized Debian images do not count as a
modified daemon; missing/changed runtime/configuration and unknown verification
output still fail closed. Cancellation retains progress without claiming that
already applied changes never occurred.

## Verification

Full suites pass: **393 Windows tests, three skips**, **395 isolated Linux tests,
16 skips**. Reports: `build/installer-tests-20261114-linux-runtime.txt` and
`build/isolated-linux/test-report-current.txt`. New orchestration tests use real
private journals but explicitly inject APT/systemd/Docker/ownership boundaries.
They cover service consent before APT, checkpoint before start, no false readiness,
foreign state, interrupted own state, configuration binding and fresh checks.

Actual current shared-executor GnuPG regression:
`build/isolated-linux/crypto-refactor-report.json` records a new clean chroot,
real package installation, an injected installer cut after APT and before journal
acknowledgement, actual continuation and synthetic encryption/decryption/repeat.
This is not power loss or interruption during dpkg.

Actual runtime packages: `build/isolated-linux/runtime-packages-report.json`.
A new Debian chroot starts without Docker/GnuPG, installs approved pinned packages,
probes actual Docker **26.1.5+dfsg1** and Compose **2.26.1-4**, verifies actual
vendor unit ownership/package integrity, and repeats without package changes.
Its checked policy prevents daemon startup. It proves package/tool behavior,
**not** application deployment, service startup or cold boot. Initial verification
correctly exposed an overly broad check of deliberately omitted documentation;
the correction was regression-tested and this clean-package test rerun successfully.

The earlier full-stack developer guest remains a separate test boundary. Current
read-only observations show Docker's API answering Linux while the fixture's
custom service remains `activating` under Type=notify. No cause is inferred from
that alone. A proposed same-version CLI repair aborted its safety precondition
before applying any package change. Earlier OCI/I/O failures remain historical
evidence, not a successful full Linux installation. No productive service, device,
release, account or paid call was touched.

Manual Linux CI includes both chroot tests; it is prepared, not dispatched.
Native packaging is recorded separately after build/source-hash verification.

## Still required

Full clean-host guided application installation plus systemd/restart acceptance,
ARM64/Raspberry Pi and Windows service acceptance remain explicitly separate.
The early public CA-store gap is superseded by
[the verified public HTTPS bootstrap](2026-11-14-installer-public-https.md).
Package/channel preparation for bare-target restore or OS-runtime repair remain
source work; this change does not silently declare those supported. Existing
prepared candidate OS variants keep their provisioning path without claiming a
new package implementation for them. Distributed/AI/voice/tutorial/local Web
administration and other open product requirements remain in the binding matrix.

Native `.20261114.8` developer builds passed version/inventory/channel smoke
execution and complete raw-source-hash matching. Evidence:
`build/native-linux-runtime-package-report.json`. Windows EXE: 12,590,017 bytes,
SHA-256 `b7bff4709b1daf9ddc0955690576e52cf3e24a284923b0e113cee203da04a575`.
Linux AMD64 archive: 14,395,545 bytes, SHA-256
`084e8102d7373c4807877573bf6e786aab2e733c2912703df3fc9dfe71de4a2c`.
Both are in `build/native-installer/` with adjacent JSON metadata, unsigned and
unpublished, explicitly `platformInstallationAccepted: false`.
