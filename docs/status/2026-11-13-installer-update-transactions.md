# Installer update transaction implementation

The overall installer assignment remains open. This records an implementation
milestone, not product acceptance or a request for user testing. ADR 0061 defines
the update authority, activation boundary and recovery constraints.

## Implemented

`--updates apply`, `resume` and `recover` use the existing authenticated staged
release, host-administrator checks and installation journal. They fence ordinary
startup, stop application writers, capture and verify an encrypted portable
backup, retain a connection-disabled PostgreSQL template snapshot, and preserve
source runtime/configuration. Target Core starts with actual Flyway migrations
under maintenance mode. Activation requires the expected schema, health, denied
application probe, preserved host/account/Space/link identities and Core audit
transition. An interrupted activation retries service start only.

Recovery clones the reserved original database without executing archived SQL or
attempting schema downgrade. It retains the failed database with connections
disabled, including after interruption immediately following its rename. It
restores retained source code/configuration and verified knowledge/recovery files,
keeping newer bytes privately before replacement. Core revokes stale sessions,
device credentials and pending commands after a data rewind. Recovery following
activation requires explicit data-loss acknowledgment and a new encrypted backup
before restoring earlier data. Completed recovery does not repeat revocations.

Native source and target service hosts must implement startup-fence protocol 1;
older unpublished development hosts fail before changes. Compose uses pinned
image identities, untagged archive loading and owned stopped retention containers
to avoid modifying shared Docker tags. PostgreSQL runtime version changes are
refused. Only same-host updates are implemented by this transaction.

## Evidence and limits

Real Core, PostgreSQL 17 and GPG process integration passed on Windows and in the
existing no-egress Linux network namespace. Both an actual synthetic Flyway V50
migration and a deliberately failing nontransactional V50 migration were tested.
Evidence includes payload-switch and activation interruptions, database-rename
interruption, wrong-password rejection before database replacement, offline owner
login after recovery, preserved identities, revoked device authority and retained
failed data. Tests execute no household actions. Runtime PE fixtures are not
executed. Service lifecycle and Windows ACL boundaries are explicitly injected;
these results are not SCM, Docker, reboot or release acceptance.

Reports: `build/update-transaction-windows-report.json` and
`build/isolated-linux/update-transaction-report.json`. Both identify the tested
Core JAR SHA-256. The Linux CI workflow now contains the same namespace test but
has not been dispatched. Core compilation and seven existing targeted security
tests passed. Installer suite: 262 tests, one Windows skip before the subsequent
three additional real-file recovery tests (which passed separately).

## Continue independently

Implement protected automatic-backup key custody, explicit maintenance-window
consent and automatic transaction continuation, then complete OS lifecycle
acceptance and distributed update barriers. The full requirements matrix remains
authoritative for all other open installer work. Existing `.5` native artifacts
predate this transaction and must be rebuilt before acceptance. Productive release
keys and publication remain external prerequisites; they do not block source
implementation or tests with isolated keys. Do not present this milestone as a
complete installer or ask for partial user acceptance.
