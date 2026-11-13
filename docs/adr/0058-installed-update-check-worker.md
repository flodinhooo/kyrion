# ADR 0058: Installed finite update checks

Status: Accepted

## Decision

Reuse the installed journal, authenticated release policy and maintenance checker.
Install a content-addressed copy of the frozen installer as a finite maintenance
worker. A daily machine task (Windows SYSTEM) or system timer (Linux root)
invokes that worker after boot and periodically without interactive login.
The worker never installs a candidate. Automatic installation requires the
separate transactional backup/migration/health coordinator, still open work.

The owner explicitly reviews the HTTPS feed and independently obtained public
trust document before enabling checks. Only administrator-protected journal
state contains settings. A revision binds each background check to its policy;
concurrent reconfiguration cannot commit a result for another channel. Existing
signed sequence, equivocation, epoch and compatibility checks remain mandatory.
Failures retain the previous successful result and record a bounded error code,
never provider output or tokens. Retired and inactive restore targets cannot
check or activate runtimes. Check configuration is not copied by restore.

Worker files are immutable and hash tracked. Fixed task definitions refuse
foreign ownership and changed executables. No shell, password, network login,
interactive desktop or user Python installation is required. Source execution
can exercise the logic but cannot masquerade as an installed native worker.
The scheduler installation is resumable and its actual activation is recorded
separately from the intended policy. Removing an installation or retiring the
source removes only its verified owned schedule.

## References and verification boundary

[Microsoft BootTrigger](https://learn.microsoft.com/en-us/windows/win32/taskschd/boottrigger)
supports repetition after machine startup; the existing strict task registration
and security descriptor implementation is extended for this fixed action.
[systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)
documents combining OnBootSec and OnUnitActiveSec. No Persistent claim is made
for a monotonic timer. Boot testing requires a disposable real target; definition
validation or an isolated process test is not cold-boot acceptance.
