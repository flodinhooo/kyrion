# KY-005: controlled host restart and off-host recovery plan

**Prepared only. No reboot, network-loss test or productive restore authorized or
executed.** Select one host and a maintenance window first; keep the other host
available as an access/recovery station. Never run old V39/V41 activation commands.
Current [evidence and backup limits](status/2026-11-07-acceptance-gates.md#ky-005--restore-isolation-and-host-recovery)
does not establish a complete external recovery point.

## Preconditions and decisions

### Read-only inventory and concrete set preparation, 2026-11-07

The existing Pi directory named `database-backups-v46-20261106T200532Z`
contains `preliminary-v41.dump` and `final-v41.dump`, not a V46 source snapshot.
Windows `E:\Kyrion\Data\backups\postgres\v46-20261106T200532Z\` ends with
`kyrion-postgres-20261106T203846Z.dump`; its verified manifest explicitly says
source schema39 and isolated target46. Directory names do not prove freshness.
Original keys/config archives exist on each source; the Pi Web and identity
tunnel were changed after that set. No current external copy was established.

For each selected installation, prepare a **new timestamped** protected set,
leaving those originals intact. Its manifest must include:

| Component | Current gap / capture in the approved quiet slot |
| --- | --- |
| Database | New consistent source-V46 custom dump, current Flyway checksums, timestamp and SHA-256; later writes/revocations omitted by old dumps |
| Keys and private configuration | Matching original credential/audit keys plus bootstrap/recovery/enrollment material and restrictive ACLs; refreshed Compose/environment/TLS/launch pins, never printed |
| Runtime | Exact installed V46 Core/JDK/parser and Web build/images plus standalone assets; retained old and candidate Web artifacts clearly separated; installed Satellite/Gateway source/unit/config and radio state |
| Knowledge | Matching document tree and byte hashes; actual previous sets were empty, so separate synthetic nonempty DB-plus-files restore proof remains necessary |
| Central identity | Independent current provider DB/config/signing state and protected tunnel credential/config; current deployment postdates old platform archive |
| Host recovery | Windows supervised startup profile/helper lifecycle and Pi startup ordering, documented access fallback; full reboot/network-loss proof remains unperformed |
| External copy | Owner-approved independent destination, capacity/access, encryption and separately recoverable key custody; off-host retrieval/checksum/decryption and isolated restore evidence absent |

Do not run the general Pi bundle-preparation script for this task: it also builds
Core and captures personal data. Windows's existing
`infrastructure/postgres/backup.ps1 -Destination <new-protected-set-directory>`
is the bounded dump entry point. On Pi use `pg_dump --format=custom --no-owner
--no-acl` inside the **inspected current platform PostgreSQL container**, using
its current configured database/user; transfer only into the selected protected
local set. Select that container by inspected ID, not an old rollout command.
Verify version46 and checksum before packaging, and keep credentials out of
arguments/logs. Coordinate a Core quiet/stop window for database-plus-Knowledge
consistency; stopping services is not authorized in the current preparation.

Create a per-file hash/size inventory without secret contents, encrypt the
complete set locally with the agreed tool/key recipient, and transfer only the
encrypted result to the explicitly selected external destination. Keep decryption
custody independent of the failed host and prove retrieval there. Then use the
existing marked network-none/tmpfs verifier and original-key domain/file checks
on a separate recovery machine, without application workers/providers. Record
actual source schema, audit/credential and revocation disposition, not only
`pg_restore` success. No transfer, backup quiescence or restore was performed here.

The owner must choose the first host (Pi or Windows), window, local-console
operator, acceptable outage and independently accessible off-host destination.
For that destination decide access, capacity, encryption and separate key custody;
no cloud account, paid service or merely another partition on the same disk is
assumed. Verify retrieval/decryption on the recovery machine before any outage.
Do not reboot a shared host without telling affected users.

1. Capture current host identity, database schema/checksums, exact image/JAR/build
   IDs and running service/start-policy inventory. Confirm no active dialogue,
   editing session, queued/running action or Calendar lease; dispose of uncertain
   work explicitly, never replay it. Finish saves and notify everyone.
2. In the later approved quiet window, take a consistent current **V46** database
   backup and matching original credential/audit/bootstrap/recovery keys, protected
   environment, Knowledge originals, launch pins, runtime binaries and restore
   instructions. Preserve the original backup set, later audit and revocations.
   The Nov6 pre-upgrade V39/V41 dumps passed software checks but omit later writes.
3. Preserve Pi installed Compose/platform.env/Caddyfile/TLS and Web rollback
   material, Gateway/Voice enrollment, radio/coordinator files and provider-pilot
   DB/config/signing material separately. A radio-file copy is not radio recovery.
   Keep Windows standalone Web/static/public assets, matching private environment,
   guarded JDK/JAR/parser, AI virtual environment, WSL speech distribution/model/
   reference paths and host firewall metadata. Do not copy models over the network
   or replace a working configuration speculatively.
4. Copy the recovery set to the approved separate destination and check checksums
   there. First restore synthetic nonempty Knowledge data. Then restore the
   actual dump only to a new isolated network-none PostgreSQL, without application
   workers, devices or providers. Verify schema, original-key audit/AEAD, document
   bytes and revocation disposition. No stale grant is fresh human consent.

## Pi restart slot

Target: `kyrion-node` / `https://kyrion-node.local`, ARM64; Docker enabled, platform
containers `unless-stopped`, user lingering enabled, Gateway and Voice/media user
units enabled. Keep current Core V46 and the owner-activated Web90125b9 build
`N6PUtpaaokUmjYzUdfjFf`. Immediate Web rollback build is
`aaUX9C2_I6tMOcrV1sImr`; no rollback is requested. Voice still depends on the
separate Windows Core.

Pi downtime also affects Pi-hole DNS, Home Assistant, Zigbee/Matter/Thread,
media and the identity pilot. Reserve a directly reachable recovery station and
known SSH host key/address; have physical console/power access if network/DNS
does not return. Do not change DNS, firewall, keys or enrollment to get green.

After owner-triggered normal host reboot, wait for host/network, Docker and
PostgreSQL readiness, then Core UP, Web healthy, HTTPS/login/static assets and
fresh intended Pi Gateway heartbeat. Docker restart policies do not guarantee
Compose dependency ordering on daemon boot: allow the existing bounded recovery
behavior, inspect failures and never delete database state or launch a newer JAR.
Inspect user-unit readiness and correct Voice destination; do not trigger audio
or a device command without the agreed human observation.

If service recovery does not converge within the agreed window (start with
10 minutes), stop acceptance and use physical console/SSH to inspect. Preserve
failed-host data/logs. Only an individually reviewed scoped service intervention
may follow; no broad Compose restart, radio restore or SQL downgrade.

## Windows restart slot

Docker Desktop and Ollama have user startup entries. Docker's Windows service is
manual/stopped while the existing user engine works. No matching scheduled task
for Kyrion Core/Web was found: **automatic unattended Core/Web startup is not
proven**. Choose supervised login/manual launch for this test, or separately
design and approve persistent startup; do not silently install a task/service.

Preserve the current guarded release under
`.run/dev-recovery/releases/v46-20261106T200532Z/`, root `core-lan.json`, protected
settings and original standalone
`apps/web/.next-master-identity-build/standalone/server.js`. The mutable checkout's
new UI/Voice source is not a replacement for those installed artifacts.

After the owner-triggered normal reboot and supervised Windows login:

1. Wait for Docker Desktop/WSL and the existing `kyrion-postgres` container; use
   existing start-only controls if absent, never recreate its data. Confirm SQL
   readiness and the source/artifact/schema checksum gate.
2. Run `infrastructure/dev/Start-CoreLan.ps1 -ValidateOnly`, then its guarded
   start only if Core is absent. It selects the original V46 artifact/JDK and
   verifies restrictive firewall guards. Do not use generic loopback bootRun or
   select the latest build against the personal database.
3. Launch the retained production Web output with the recorded Node executable,
   `infrastructure/dev/web-env.cjs`, original private configuration and loopback
   port3000. Validate the launch profile before the window. Do not run a new build
   in the retained output or silently replace it with `pnpm dev`.
4. The independent recovery helper is currently not listening. Start it only in
   the chosen supervised operator session with its protected key/settings, then
   use existing start-only recovery for missing AI/Ollama/STT/TTS. Do not restart
   running WSL/speech processes. Its ACL commands work on an owned synthetic path;
   the historical helper-start failure has not been reproduced on a live helper.
5. Check all seven health endpoints, Web DE/EN/login/assets, Pi→Windows guarded
   reachability, actual destinations and fresh intended Gateway heartbeat.
   A ready service is not authenticated user, audible output or actuator proof.

Allow at least15 minutes for supervised login and cold speech initialization;
record the actual time rather than promising a bound. A missing launch profile,
failed guard/ACL or unreachable key/config blocks the test. Restore access using
the known local operator account/console and retained runtime, not weaker ACLs.

## Recovery boundary

Never overwrite a running personal database. Retain the failed installation,
restore to a separately named isolated destination and use a runtime matching
that exact schema. No application/worker starts until original keys/files,
provider effects and later revocations have been reconciled and explicitly
approved. V39/V41 snapshots are not directly usable with the current V46 runtime.
Database restore cannot undo real device/provider effects. Do not resurrect old
sessions/grants or replay pending work automatically. Off-host recovery and full
host restart remain separate acceptance records; KY-005 stays open until both pass.

## Subsequent local V46 preparation, without interruption

The earlier inventory above is historical. A new Pi online V46 source dump now
exists at `~/.local/state/kyrion/database-backups-v46-20261107T175611Z/`, with
matching installed runtime archives in the corresponding `recovery-material-`
directory and original keys/private effective runtime configuration separately
in `~/.local/share/kyrion/recovery-secrets/20261107T175611Z/`. All are owner-only;
previous sets remain intact. Nothing was transferred off Pi.

The [post-activation evidence](status/2026-11-07-acceptance-gates.md#additional-local-pi-v46-snapshot)
records the dump checksum, isolated source-V46 restore, original-key audit and
credential proof, initial failed proof attempt and final passing results.
The database snapshot is transaction-consistent; files and runtime metadata were
captured online without global quiescence. Actual Knowledge was empty, so no
nonempty document restore is established. This local set is not proven encrypted
and is not an off-host or complete-host recovery acceptance.

Before promoting it to a complete recovery set, add current root-protected
installed Compose/environment/TLS under the owner's administrative session,
without substituting the old deployment archives. The effective container
configuration captured here is useful evidence, not the original installed
configuration. Reconcile a separately owned current identity/provider backup;
this follow-up did not touch Identity or DNS. Agree encryption/custody and an
independent destination, then verify retrieval/decryption and isolated recovery
there in a separately authorized task. No host reboot, service stop, productive
restore, expired command replay or hardware/audio acceptance happened here.
