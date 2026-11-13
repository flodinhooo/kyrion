# Installer continuation: Linux startup and update fences

The complete installer assignment remains open. This is development evidence,
not a request for user acceptance or a declaration of platform release readiness.

## Implementation

ADR 0066 preserves an existing installation's identity provider on continuation;
an explicit conflicting override fails before provisioning/account operations.
Fresh defaults remain the already existing Kyrion issuer/client. Six regressions
cover saved policy validation, explicit selection and actual local CLI journals.

ADR 0067 adds a protected native Linux maintenance worker, generated tracked
Compose restart overlay and installation-owned systemd startup service. The
downloaded frozen installer configures it during setup, completed restore and
repair; maintenance supports `--autostart enable|disable|status`. Registration
uses the same installation lock and journal. Retirement disables it; removal
deletes only its verified owned unit. Disable leaves running components intact.

Machine/daemon bindings prevent accidental clone or changed-daemon startup.
Incomplete updates, prepared restores and retired installations defer startup.
The maintenance Compose override remains last, so normal container restart
settings cannot override migration isolation. An active older update worker must
advertise the corresponding startup capability before startup registration;
explicitly disable/reconfigure that owned schedule with the current native
installer when upgrading it. Feed/trust settings are never silently replaced.

Three systemd attempts are allowed, including the initial start, even for slow
failures. Each normal startup records a nonhealthy pending checkpoint before
starting components; a failed attempt cannot preserve an earlier healthy result.
An interrupted update retains its separate bounded continuation budget and
existing explicit recovery procedure. There is no generic schema downgrade.

## Actual isolated systemd evidence

The explicitly owned Debian 13 WSL development guest now runs systemd 257.13,
Docker 26.1.5 and Compose 2.26.1. Docker runs in its own private network namespace;
no developer Docker Desktop container or other distribution is modified.
These are guest development tests, not physical cold boot or Windows pre-login
acceptance. No production installation or release is created.

`tests/integration/verify-update-units.py` validates actual notification,
automatic-update and startup definitions using `systemd-analyze verify` and the
real standalone executable. Report:
`build/isolated-linux/systemd-definitions-20261114-1.json`.

`tests/integration/verify-linux-startup.py` registers a newly owned fixture unit,
invokes the frozen worker under real systemd and verifies durable update deferral.
It alters only that fixture's worker, observes three rejected executions and a
stable failed unit, then removes that exact unit. It never starts an application
stack. Report: `build/isolated-linux/systemd-startup-20261114-1.json`.
The initial test incorrectly expected `Result=start-limit-hit`; this systemd
retains `Result=exit-code`. Actual journal invocation count, restart count and
stable stopped state establish the bound. This test correction does not change
the production retry limit.

The tested `.20261114.1` worker hash is
`4f474bb6d374d0727601c63829b4bfd076ba8d441a6693e1d33295f28429520c`.
It predates subsequent startup-capability/restore/repair additions, so those need
the current build and repeated developer checks. Successful full application
boot, guest reinitialization, physical reboot, Windows SCM and ARM hardware are
separate outstanding acceptance boundaries.

## Continuing work

The full current regression suites pass: **329 Windows tests (three skips)** and
**331 isolated Linux tests (16 skips)**; Ruff and Git whitespace checks pass.
The restricted Windows run could not exercise real protected ACL mutations;
the repeated ordinary developer-context run passed those tests. Neither run
registers a Windows service or establishes administrator/cold-boot acceptance.

The requirement matrix remains authoritative. Full local management, enrolled
installer nodes, runtime/model lifecycle, voice, adaptive tutorial, remaining
disaster recovery paths and end-to-end product journeys remain open source work.
Missing platform hardware must not be confused with those missing implementations.
Continue with actual complete stack startup/update/recovery checks and the
remaining independent requirements; do not ask the user to test this milestone.
