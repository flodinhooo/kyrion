# Owned Linux guest init restart

The full installer task remains open. This checkpoint adds platform evidence;
it does not request user acceptance or close physical boot/Windows requirements.

The native `.20261114.24` installer configures its owned service on the completed
Debian 13 AMD64 fixture. The test records application identity, local user,
PID-1 start ticks and kernel boot ID in a private checkpoint. It leaves only
the owned unit enabled, stops application containers, and restarts only the
registry/path-verified workspace WSL distribution. No global WSL shutdown,
Docker Desktop restart, foreign distribution or productive target is touched.

The actual new PID-1 process starts the enabled service through systemd after
Docker. The frozen worker establishes application/TLS health. Database identity
is unchanged, and the same local user logs in with no network default route.
No interactive Linux login, readiness mock or injected systemd probe is used.
Successful cleanup removes only that owned unit/drop-in and stops its project;
data, images, encrypted backups and private test access remain preserved.

An initial test incorrectly required a changed kernel boot ID. WSL can restart
one distribution while retaining the shared VM kernel. That initial invocation
is failed evidence, not a product fix. The corrected test proves changed PID-1
start ticks and explicitly reports `sharedKernelRestarted: false`,
`physicalColdBootVerified: false` and `windowsPreLoginBootVerified: false`.
Launching this WSL guest still requires the existing Windows user session.

The reusable `tests/integration/verify-guest-init.py` two-phase test also passes
through a second real guest restart. Supply an explicit unique `--attempt UUID`
to each pair of phases. It never initiates a reboot itself:

```text
verify-guest-init.py prepare --root MARKED_FIXTURE --worker FROZEN_INSTALLER --attempt UUID
# Verified fixture host driver restarts only its own guest and waits for the unit.
verify-guest-init.py verify --root MARKED_FIXTURE --attempt UUID
```

Run each phase under the marked fixture's Docker network namespace, as with
the existing complete systemd test. The guard requires the private `/work`
fixture markers, successful installed-backup evidence and completed recovery.
Failed verification leaves the owned state available for diagnosis; success
cleans up its unit and writes a unique report. Neither this test nor the prior
service-start test certifies physical power loss, standby, Raspberry Pi/ARM64
or Windows service startup before user login.

Evidence: `build/isolated-linux/guest-init-source-prepare.txt`,
`guest-init-source-verification.txt`, plus the unique guest fixture report.
The earlier corrected driver also records `guest-boot-verification.txt`.
The source-only integration addition passes Ruff/format checks; the actual
two-phase run is its behavioral test. Existing installer regressions remain
480 Windows tests (nine skips) and 488 isolated Linux tests (twenty skips).

Continue the existing node/enrollment and task-distribution gaps next. Gateway
and voice identities already exist and must be reused; this checkpoint creates
no new account, Space, identity service or public endpoint.
