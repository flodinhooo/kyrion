# ADR 0069: Installed consistent backup scheduling

Status: Accepted for implementation, 2026-11-14.

Automatic operational backups are an explicit installer requirement. Reuse the
existing installation journal, privileged native worker, consistent capture,
GnuPG format, archive validation and protected recovery-key custody. Do not add
another account/Space store, backup encryption envelope or cloud dependency.
This concerns platform maintenance; existing personal exports remain separate.

An administrator explicitly approves a UTC window, selected weekdays, retention,
protected external local store and separately exported recovery key. No default
automatic backup is silently enabled. Reuse the protected maintenance backup key
when present; never overwrite it. Reject a key export inside the installation or
backup store. Store a protected installation-bound marker so a missing removable
volume cannot silently fall back to an ordinary directory at the mount path.

Use an installation-owned systemd timer or SYSTEM boot task invoking the same
frozen executable with a fixed backup entrypoint. Validate worker hashes and
owned definitions. Backups need no release feed and work without internet.
Schedule checking is every fifteen minutes and after boot; the selected UTC window determines
whether a new backup starts. Already approved interrupted work may finish outside
the window, within a durable three-attempt budget. No unattended restore occurs.

The worker acquires the existing installation lock, respects update/restore
authority fences and uses existing bounded service quiescence. Resolve a pending
owned service pause before consulting the external store or window, reserving
at most three durable automatic service-recovery attempts. Explicit maintenance
may retry after exhaustion; never start services across an authority/update fence. Journal capture,
verification and completion. Authenticate/decrypt and inspect a published backup
before marking it complete; an archive alone is not full application restore
acceptance. Retry published-but-unacknowledged output through verification rather
than overwrite it. Bind its authenticated metadata to the exact backup-run UUID;
a compatible older archive is not a fresh backup. Record stable errors without
secret or provider output, including storage failures before capture starts.

Linux Core restoration must confirm current health of the image-pinned,
installation-owned container and its exact knowledge bind before clearing the
durable pause obligation. A successful Compose start request is not sufficient.
Reuse the same bounded daemon readiness checks as database startup, with no
arbitrary service-name input and no authority/update-fence bypass.

Prune only after a new backup is verified and its receipt is durable. Remove only
recorded files with matching hashes from the authenticated owned store, retaining
the requested number of successful backups. Unknown/changed files and other
stores are never removed. Unavailable storage or failed retention is visible;
do not accumulate new captures indefinitely while retention is blocked.

Disabling, uninstalling and retiring remove only the owned schedule. They retain
external backups and their key exports. Restoring an installation does not
silently activate an old host's backup schedule. Actual OS task execution and
physical reboot acceptance remain separate from generated definitions and tests.
