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

## Prepared completion of the local V46 set

`dbdc8de` and the existing V46 checksum/isolated-restore/original-key proof are
preserved. Those checks were **not repeated** during this preparation.

### Actual additional capture and the remaining privileged files

The running Caddy container already has read-only mounts of the installed
Caddyfile and TLS directory. Without adding mounts, changing privileges or
restarting it, those existing views were captured into an additional owner-only
archive at:

`~/.local/share/kyrion/recovery-secrets/20261107T175611Z/additions-20261107T193554Z-d8d1ddc2/caddy-current-config-tls.tar`

The archive contains exactly these source files, with original ownership/modes
recorded in its protected metadata:

| Source on Pi | State in the additional set |
| --- | --- |
| `/etc/kyrion/platform/Caddyfile` | Captured through existing read-only `/etc/caddy/Caddyfile` mount; explicit certificate/key paths, no external Caddy import |
| `/etc/kyrion/platform/tls/server.crt` | Captured; SHA-256 matches retained TLS pin |
| `/etc/kyrion/platform/tls/server.key` | Captured without printing/exporting it; derived public key matches the certificate |
| `/etc/kyrion/platform/compose.yml` | **Still missing as a current host-file copy**; effective runtime metadata is not a replacement |
| `/etc/kyrion/platform/platform.env` | **Still missing as a current host-file copy**; contains protected deployment configuration |

The observed TLS directory has only server.crt/server.key. This deployment uses
an explicit pinned self-signed server certificate, not a newly created recovery
CA/key. Preserve that existing certificate trust on the recovery station; do not
regenerate it silently. Caddy `/data` and `/config` remain runtime caches/state,
not substitutes for the explicit TLS files and installed configuration. Additional
unknown imports/mounts found during a later root capture require inventory review.

The matching current Caddy image was also archived, and the already compiled
`VerifyOriginalData.class` plus its public Java source retained, under:

`~/.local/state/kyrion/recovery-material-v46-20261107T175611Z/additions-20261107T193554Z-d8d1ddc2/`

The new image archive's config digest matches the live Caddy image; its protected
manifest indexes its bytes and hashes. Only these new additions were verified.
Their directories/files are `0700`/`0600`. Previous dumps, keys, runtime archives and
manifests were not overwritten. Current total local payload is 958704940 bytes
(about 914 MiB), excluding the still-pending root addition.

Noninteractive sudo still requires a password. The reviewed capture helper is
staged at `~/.local/state/kyrion/ky005-recovery-preparation-20261107/` and is also
versioned as `infrastructure/postgres/capture-pi-recovery-config.py`. In an
interactive Pi SSH terminal, the concrete authorized capture step is:

```sh
sudo /usr/bin/python3 /home/flodinho/.local/state/kyrion/ky005-recovery-preparation-20261107/capture-pi-recovery-config.py capture
```

It captures the five required files and any additional regular TLS files into a
**new** root `0700` directory below `/var/backups/kyrion/local-v46-additions/`, with
copies/manifest `0600` and original UID/GID/mode/hash metadata. It rejects redirected
paths, symlinks and changing sources. Failure retains an INCOMPLETE addition;
no source settings or services are changed. Success prints only the new path.
Three synthetic helper guard tests pass. Compare its fresh Caddy/TLS hashes with
the mounted-view addition before selecting the recovery version; a mismatch is
configuration drift to review, not permission to overwrite either source.
This capture is current configuration evidence, not a simultaneous DB/files cut.

### Encryption: tested mechanism, unresolved recovery-key custody

Installed tools: GnuPG 2.4.7/libgcrypt 1.11.0, OpenSSL 3.5.6, GNU tar 1.35,
Python 3 and Docker 26.1.5. age is not installed; no package or key was installed.
`test_recovery_encryption.py` used only a synthetic tar and an ephemeral synthetic
passphrase in a temporary GPG home: AES256 encryption/decryption round trip
matched; a wrong passphrase and altered ciphertext both failed. Its own agent
was stopped and scratch removed. No real recovery key was created or personal
backup encrypted. OpenSSL was used only to compare the captured TLS public keys.

The owner still must choose an independently available recovery secret/custodian:
either an approved high-entropy passphrase recoverable without this Pi, or an
already controlled recipient key with verified fingerprint and independently
recoverable private key. No recipient, passphrase, storage account or custody
location is assumed. Do not put a personal recovery secret in arguments,
environment values, Git, chat or the encrypted payload itself.

After the root capture succeeds AND the owner chooses the passphrase route and
custody, the following is the prepared **local-only** encryption procedure.
It is not authorized execution of an unchosen key scheme. Use an interactive
Bash terminal; GPG prompts through its pinentry/TTY. Do not enable shell tracing.
Set ROOT_ADDITION to the successful capture's exact output path first:

```bash
set -euo pipefail
umask 077
ROOT_ADDITION=/var/backups/kyrion/local-v46-additions/REPLACE_WITH_SUCCESSFUL_CAPTURE
[[ "$ROOT_ADDITION" =~ ^/var/backups/kyrion/local-v46-additions/[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$ ]] || exit 1
[[ -t 0 && -t 1 ]] || exit 1
sudo test -f "$ROOT_ADDITION/manifest.json"
sudo test ! -e "$ROOT_ADDITION/INCOMPLETE"
OUT=$(mktemp -d /home/flodinho/.local/state/kyrion/encrypted-v46-XXXXXXXX)
export GPG_TTY=$(tty)
sudo -v
sudo tar --create --file=- --directory=/ -- \
  home/flodinho/.local/state/kyrion/database-backups-v46-20261107T175611Z \
  home/flodinho/.local/state/kyrion/recovery-material-v46-20261107T175611Z \
  home/flodinho/.local/share/kyrion/recovery-secrets/20261107T175611Z \
  "${ROOT_ADDITION#/}" \
  | gpg --no-options --no-symkey-cache --cipher-algo AES256 \
      --symmetric --output "$OUT/recovery.tar.gpg.partial"
mv --no-clobber -- "$OUT/recovery.tar.gpg.partial" "$OUT/recovery.tar.gpg"
(cd "$OUT" && sha256sum recovery.tar.gpg > SHA256SUMS)
```

Only ciphertext and its checksum are candidates for a subsequently approved
transfer. No combined plaintext tar is written on the source. Retain partial
ciphertext as incomplete on pipeline failure; do not promote it. For an existing
recipient-key decision, separately use the verified selected fingerprint with
public-key encryption instead of improvising a passphrase or generating a key.
A successful synthetic test is not personal-custody or disaster-recovery proof.

### Prepared independent off-host rehearsal

No off-host destination is selected and no personal material was sent anywhere.
The destination must be independently accessible if the Pi/its SD card/network
is unavailable; another directory/partition on the same Pi is insufficient.
Agree owner/operator, allowed data location/access, encrypted storage and deletion
policy. Provide at least 10 GiB free for the current roughly 914 MiB payload plus
pending configuration, cipher/plaintext staging, image import and logs. Recompute
for a new/nonempty Knowledge set: reserve encrypted input + plaintext archive +
expanded quarantine + imported image layers + restore scratch/headroom. Use at
least 2 GiB available RAM for the small current proof; cap the fixture's tmpfs and
verifier heap instead of assuming host resources are free.

The prepared runtime target is independent Linux ARM64 with Docker Engine 26+
(or separately validated ARM64 emulation), Python 3.12+, GNU tar, GnuPG 2.4+,
and checksum tooling. Reviewed archived Core/PostgreSQL/Caddy/Web images and the
compiled read-only verifier are available without new builds, pulls or speech
models. Existing original credential/audit keys travel only inside the approved
encrypted payload; its decryption secret/private key must be independently
retrievable. These are distinct keys. Verify the TLS certificate trust separately
if a later, separately authorized application/TLS rehearsal is selected.

On that approved target, set `umask 077` and use a new `0700` quarantine on encrypted storage:

1. Check the ciphertext SHA256SUMS. Decrypt to `recovery.unverified.tar` using
   the chosen independently supplied key, for example
   `gpg --no-options --no-symkey-cache --output recovery.unverified.tar --decrypt recovery.tar.gpg`.
   Promote only after GPG exits 0. GPG can emit plaintext before reporting an
   integrity failure: never extract/promote failed output; keep it protected.
2. Before extraction, inspect every tar member with Python tarfile. Reject
   absolute paths, `..` components, links, special files, duplicate paths and
   setuid/setgid modes; require only the three selected home backup roots and
   the selected root-addition prefix. Then extract only below the quarantine,
   unprivileged with `--no-same-owner`, never into `/` or a live installation.
3. Verify the existing set manifest and separate addition/root manifests using
   their relative file mappings, including original dump/keys/runtime hashes.
   Do not silently choose between mismatching mounted-view and host-file copies.
   Verify image archive config digests against the recorded image IDs before
   `docker load` of only those images; no existing service gets recreated.
4. Create a uniquely named marked PostgreSQL container from the archived exact
   PostgreSQL image, `--network none`, no published ports, no persistent mount,
   `--tmpfs /var/lib/postgresql/data:rw,nosuid,nodev,size=768m`. Trust auth is
   confined to this unpublished disposable fixture. Record its exact ID and
   unique rehearsal label. Wait for final PostgreSQL PID1 plus pg_isready.
5. Restore only into that fixture using
   `docker exec -i "$RECOVERY_DB_ID" pg_restore --exit-on-error --no-owner --no-acl -U kyrion -d kyrion < "$RECOVERY_DUMP"`.
   Check 46 successful migrations, zero failed migrations. The source installation
   is never contacted. Do not run Compose, a Spring context, workers or providers.
6. Expand only BOOT-INF/classes and BOOT-INF/lib from the verified app.jar into
   the quarantine. Run the retained VerifyOriginalData.class with those libraries
   using Java 21 from the archived Core image, overriding its entrypoint to
   `/opt/java/openjdk/bin/java` and its command to `-cp ... VerifyOriginalData <settings>`.
   Use `--network container:$RECOVERY_DB_ID`, read-only root and backup/key/file
   mounts, `--cap-drop ALL`, no-new-privileges, bounded tmpfs and `-Xmx256m`.
   Match the quarantine owner's UID/GID so protected files remain readable
   without changing their permissions. Settings point only to 127.0.0.1 inside
   the isolated namespace, the restored DB and readonly recovered keys/files.
   Verify audit chains, credential AEAD and document byte hashes. Preserve
   original revocations; never interpret restored grants as new consent.
7. First exercise a separate synthetic **nonempty** Knowledge DB/files fixture;
   current personal Knowledge is empty. No actual ingestion/RAG, account login,
   device/provider action or production restore is implied by the verifier.
   Record independent-host identity, key retrieval/decryption, hashes and proof.
   Remove only the exact positively identified rehearsal container IDs, and
   handle decrypted quarantine under the agreed data retention policy.

The preceding is prepared procedure, not an executed off-host proof. Target and
key decisions remain required; do not transfer personal backups to this machine
until both are explicitly settled. Existing same-host proof is not repeated now.

### Smallest coordinated database/files quiet window

Source inspection of [object storage](../services/core/src/main/kotlin/dev/kyrion/core/knowledge/storage/KnowledgeObjectStore.kt),
[upload/delete orchestration](../services/core/src/main/kotlin/dev/kyrion/core/knowledge/application/KnowledgeService.kt)
and [ingestion/cleanup](../services/core/src/main/kotlin/dev/kyrion/core/knowledge/ingestion/KnowledgeWorker.kt)
finds these coupled writers:

- Upload writes/fsyncs `.upload-*.tmp`, atomically moves the original to its UUID
  filename, parses/hashes it, then commits document/job rows. A file can exist
  before its DB row; checking only SQL job counts does not prove no upload.
- Ingestion claims/renews leases and commits status/chunks/embeddings, with audit
  writes. Reindex changes revisions/jobs. A worker batch can call an embedding
  runtime; do not interrupt a running job simply because one request timed out.
- Deletion first tombstones the DB; cleanup removes the file then its row.
  Scheduled sweep deletes old temporary/orphan files. Freezing upload UI alone
  leaves both worker cleanup and sweep running.
- Other Core HTTP requests, calendar leases/scheduler, gateway command results,
  activity/audit, credential/account mutations and host-local recovery operations
  can still write the database or keys/configuration. Coordinate users and
  privileged operators, not just a browser tab.

Only Core currently mounts `/var/lib/kyrion/knowledge`. A read-only observation
found zero Knowledge documents/jobs/tombstones, active calendar leases, pending
actions, nonterminal gateway commands, active Pi voice sessions and other active
DB clients. These are dated observations, not a future stop authorization or an
HTTP in-flight counter. No uploads/actions may be started in the future slot.
The actual packaged Spring Boot metadata defaults to graceful shutdown and 30s
per lifecycle phase; no corresponding environment override was present.

Prepare static configuration/runtime images and the encryption destination
before the slot. The minimum practical boundary with the existing implementation
is **only the Pi Core process**, not Web/Caddy/PostgreSQL/host or Satellite:

1. In a separately authorized window, finish user edits/uploads/dialogues and
   device/provider actions; freeze new mutations and root key/config edits.
   Recheck the above job/lease/action counters and in-flight work. Do not clear
   leases, remove pending work or replay uncertain commands to get a green count.
2. Record the current Core container ID/image/config, then gracefully stop that
   exact existing container with a 90s stop allowance. This is a prepared step,
   **not executed here**. Confirm the process is stopped, exit code is not 137,
   OOMKilled is false, no second writer/client remains and no parser child is
   active. A forced/uncertain stop invalidates automatic consistency acceptance.
3. While Core remains stopped, create a **new** timestamped V46 dump, copy the
   complete Knowledge root including any pending temporary/orphan files, and
   capture matching original keys/configuration. Do not reuse the older online
   dump with a newly copied nonempty document tree. Record file inventory/hashes
   and repeat file metadata after capture; no writer or changed file is allowed.
   Database read-only checks must show expected schema and no foreign writer.
4. Once those small copies are complete and the source file inventory remains
   stable, start only the same original Core container/image/config. Record UP,
   V46 validation and fresh intended heartbeat; issue no audio/device/provider
   acceptance command. If state is uncertain, inspect rather than recreating
   services, weakening guards or restoring over production.
5. Do slow image export, encryption and isolated/off-host verification **after**
   Core is available again. A new coordinated snapshot is a new reason to verify
   its checksum/restore/keys/files; it never overwrites the 175611Z online set.

Reserve 5 minutes for the current tiny DB/empty file tree; the practical service
outage is Core drain + dump/file capture + restart/readiness, not image export or
encryption. Duration is a planning budget, not a measured bound; abort/reassess
if work does not drain. Web/Caddy stay running, but Core-backed Web functions and
Pi device commands are unavailable during the slot. No Core stop/start, host
restart, Web/Satellite/binding/Identity/DNS change occurred during preparation.
