# ADR 0067: Supervised Linux platform startup with the existing installer

Status: Accepted

Docker daemon startup alone does not provide a verified ordered platform start.
Add an owned systemd oneshot service that invokes a protected copy of the current
native installer. No Python interpreter is required on the installed host. The
background entrypoint validates the same private installation journal, host
binding and existing authority/update fences before starting the owned Compose
project with dependency/readiness checks. Inactive restore/retired or unfinished
update states are deferred; they must never be reported as healthy.

Use a generated tracked `compose-startup.yml` overlay for bounded
`on-failure:5` container restarts. This preserves existing primary configuration
and image pins. The supervisor starts dependencies in order after Docker; the
maintenance override's `restart:no` remains higher priority during migrations.
Existing programmatic/source provisioning remains a developer path; the downloaded
native guided installer registers the boot service and offers later maintenance.

Copy a running frozen Linux executable through `/proc/self/exe`, not a mutable
download pathname. Record its hash in the existing file journal. Reuse the same
maintenance executable namespace as update workers and validate its advertised
Linux-start capability before registration. Require root-owned paths, exact
owned-unit hashes and the existing local rootful Docker locality checks. Bind
startup metadata to the salted local machine identity and daemon ID; changed
hosts require an explicit restore/migration rather than accidental clone startup.

Systemd service registration and enablement are checkpointed and idempotent.
The service has finite execution/retry limits; current container health is distinct
from its historical successful oneshot state. Configure it without starting a
second lock-owning worker while the installer holds its lock. Explicit disable
affects future boot; application removal also removes only the owned unit.
Source retirement disables that unit before issuing the existing transfer receipt.

This adds no account, Space, general enrollment agent or competing authority
database. Guest-init/systemd tests, container integration, physical cold boot,
Windows pre-login startup and Raspberry Pi acceptance remain separate evidence.
