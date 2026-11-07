# KY-005: controlled host restart and off-host recovery plan

**Prepared only. No reboot, network-loss test or productive restore authorized or
executed.** Select one host and a maintenance window first; keep the other host
available as an access/recovery station. Never run old V39/V41 activation commands.
Current [evidence and backup limits](status/2026-11-07-acceptance-gates.md#ky-005--restore-isolation-and-host-recovery)
does not establish a complete external recovery point.

## Preconditions and decisions

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
units enabled. Keep current Core V46 and Web871c46a build
`aaUX9C2_I6tMOcrV1sImr`. Voice still depends on the separate Windows Core.

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
