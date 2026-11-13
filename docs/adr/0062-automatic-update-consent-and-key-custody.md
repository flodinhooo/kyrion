# ADR 0062: Automatic update consent and backup-key custody

Status: Accepted

Automatic installation is opt-in and uses the existing update worker and
transaction, not another privileged daemon. Consent binds a signed-feed policy
revision, UTC weekly maintenance window and maximum artifact download size.
The installer displays downtime, backup custody, license-review responsibility
and the fact that a started transaction may finish outside the window. Windows
and Linux schedule checks hourly when enabled, with finite two-hour invocations;
ordinary notification-only checks retain their daily ten-minute schedule.

A generated backup passphrase lives in a separate host-administrator-only
directory, never Core's readable secrets directory or the journal. Exclude it
from portable backup. Enabling requires an exclusive protected export outside
the installation; the owner must retain that export separately for disaster
recovery. Keep the key when disabling automatic updates because existing backups
still depend on it. Do not print or include the key in diagnostics.

Only the already verified installed worker can enable this policy. Changing the
signed feed/trust revision invalidates unattended authorization until explicitly
renewed. Persist automatic approval in the transaction before application
shutdown. After interruption, only that automatic transaction and matching policy
may resume without interactive password entry; manual transactions remain manual.
Resumption completes an already approved transaction even outside its start
window, without fetching a newer candidate. Never perform unattended database
rewind or acknowledgment of post-activation data loss. Failures preserve the
startup fence and require the existing explicit recovery flow.

UTC is explicit in the initial terminal interface; no silent local-time or DST
interpretation is made. Distributed maintenance barriers remain a separate
requirement and are not satisfied by a single-host schedule.
