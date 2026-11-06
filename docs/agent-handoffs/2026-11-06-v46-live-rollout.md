# Windows and Pi V46 live rollout

Date: 2026-11-06. The owner explicitly requested live rollout on both existing
installations after Identity source integration and archive cleanup. This record
supersedes earlier statements that the personal databases remain V39/V41 or that
no runtime activation occurred. Hardware/provider acceptance remains separate.

## Result

| Installation | Before                               | Live result                                                                                           |
| ------------ | ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Windows      | V39, old guarded Core, Web not ready | V46, reviewed Core and production standalone Web; PostgreSQL/Web/Core/AI/Ollama/STT/TTS ready         |
| Pi           | V41, previous Core/Web images        | V46, new native ARM64 Core/Web healthy; existing PostgreSQL and Caddy containers retained and healthy |

Windows Web is available at `http://localhost:3000/`; Pi Web at
`https://kyrion-node.local/`. The existing local product-website preview on 3001
also returned HTTP200. No deployment to public `kyrion.ch`, DNS modification,
productive central-provider setup, installer change, OS upgrade, firmware change,
host reboot or deliberate provider/device action was performed.

The optional central login remains **disabled on both live Cores** because no
productive provider configuration was supplied. Local accounts remain independent.
There is no automatic account merge, Space membership or OWNER assignment. Cloud
invitations remain the next implementation slice, not deployed functionality.

Owned restore-database containers were stopped after verification, their named
recovery volumes/backups retained. Two stopped stateless Pi drill containers were
removed after preserving their logs privately. No live database/container or
unrelated Docker resource was removed by this cleanup.

## Exact source and artifacts

Application source baseline is master `1d98a73`, including the entire Identity,
Calendar and Gateway integration. This rollout adds operator verification tools,
one migration-tool correctness fix and its regression; application main-source
and migration SQL bytes remain unchanged. Source commit IDs for this work are
discoverable from this file and the operator-tool history.

Operator fix/tools/regression commit: **`993688a`**. The documentation closeout
commit is discoverable with `git log -- docs/agent-handoffs/2026-11-06-v46-live-rollout.md`.

- Core JAR on **both** installations:
  `f73b47d1c55cc717804a77c88f07d23cf3ab807dc7714b03fb5e9f543b865130`.
  Compared to the previously reviewed JAR, re-built JAR and actual live Pi file.
- Windows active guarded Core PID at acceptance: `49944`, immutable runtime copy
  under `.run/dev-recovery/guarded-start-45bc96d4-a0ba-440d-a5f8-ed39e73d74ec/`.
  Existing guarded JDK21 and effective firewall restrictions were preserved.
  The recovery manifest/settings now select the reviewed V46 release; the
  Knowledge parser path is pinned to its matching immutable release copy.
  All other private environment entries and original key files were retained.
- Windows production Web PID at acceptance: `25344`, tested
  `.next-master-identity-build/standalone/server.js`, with its required static and
  public assets. It binds only loopback3000 and uses the original Web configuration.
- Pi Core `kyrion/core:identity-v46-20261106t200532z-r2`, native ARM64 image ID
  `sha256:18744128139c5e3bd453cef3ec3739fce77debfc2c823ccffcc8d508b6806137`.
  It packages the reviewed JAR/parser in a freshly resolved Java21 runtime with
  curl for the existing healthcheck. The earlier preparatory candidate was not
  activated. No gateway-agent replacement was needed.
- Pi Web `kyrion/web:identity-v46-20261106t200532z`, native ARM64 image ID
  `sha256:dfe4dfa0c12b470ae6463db3ae2c7e49a8f7219c8ff8efbb0b75a7ebf7174634`.
  Built on the actual Pi from an archive of the reviewed Web tree, with the frozen
  lockfile; Windows node_modules/build output were not copied into it.

PIDs are observations, not permanent identifiers. Original pins, JAR, installed
Compose/env and old image references remain protected recovery material.

## Recovery, maintenance and migration proof

Separate original recovery sets were prepared for Windows and Pi. Their databases
and keys were never exchanged or merged. Pi private data/keys/configuration stayed
on the Pi. Protected directories/files use restricted ACLs or POSIX0700/0600;
database dumps are kept separately from original-secret storage.
These are protected local software-rollout recovery sets; an off-host disaster
recovery copy/acceptance was not performed or inferred from the local drills.

Windows protected locations:

- SQL backups: `E:/Kyrion/Data/backups/postgres/v46-20261106T200532Z/`;
  final approved dump `kyrion-postgres-20261106T203846Z.dump` and companion manifest.
- Original keys/configuration/Knowledge/old runtime and ACL records:
  `E:/Kyrion/Data/backups/protected-recovery/v46-20261106T200532Z/`.
- Private operator evidence: `.run/stabilization/live-rollout-20261106T200532Z/`.
- New pinned release: `.run/dev-recovery/releases/v46-20261106T200532Z/`.

Pi protected locations below the existing operator's home:

- SQL backups: `.local/state/kyrion/database-backups-v46-20261106T200532Z/`,
  including `final-v41.dump` and verified manifest; final SHA-256
  `4d0522aeb065457d1c8b2b325e20dc5fe966721ecadd18ec16ba4ed30279e38c`.
- Original configuration, TLS, keys, Knowledge, Gateway and Voice recovery:
  `.local/state/kyrion/recovery-v46-20261106T200532Z/`.
- Native build/operator evidence:
  `.local/state/kyrion/rollout-v46-20261106T200532Z/`.
- Existing coordinator/configuration/database radio files were copied read-only
  into protected recovery storage. This was not a radio restore or consistency/
  physical acceptance test. No radio state was changed.

Actual custom-format dumps were independently restored into new storage on
internal Docker networks. The original installations were never scratch targets.
Separate V39/V41 rollback copies were retained. `VerifyOriginalData.java` loads
only the reviewed artifact's domain verifiers and supporting libraries, without
a Spring context/provider clients: it checks real audit chains using the original
HMAC key, real AEAD credentials using the original credential key, and referenced
Knowledge originals. Both current installations contain **zero Knowledge
documents**, so no claim of a nonempty live document recovery test is made.
Adapters' deliberate zero-byte credential placeholders are counted separately.
Wrong-audit-key and wrong-credential-key negative checks rejected correctly.

Frozen pre-activation proof:

- Windows: two audit chains, 8,937 sealed events, 874 retained legacy events,
  five decrypted credential records, eleven secret-less device references.
- Pi: four audit chains, 871 sealed events, 874 retained legacy events,
  three decrypted credential records, six secret-less device references.
- Final post-start original-key verification passed as well. New normal startup/
  background audit events are expected; old histories were not rewritten.

For each final live apply, scoped writers/ingress were paused, no unresolved
device work or active Calendar leases were allowed, competing DB clients were
absent, and a fresh final dump was restored again. Every source table digest and
historical checksum matched that independent final copy before apply. The
schema-only tool bound artifact/tool/catalog/plan hashes and the actual target.
Windows applied exactly seven migrations V40–V46; Pi exactly five V42–V46.
No migration was edited, repaired, dropped, baselined or replayed out of order.
All expected additive tables started empty; no new identity links/users/roles
were provisioned. Existing-account/Space/role/grant digests also matched after
activation. Existing permissions and single-Space restrictions remain effective.

Normal Core startup validated the complete V1–V46 catalog. Windows' normal
runtime gate additionally reported no missing/mismatched migrations or active
sync leases. Both live Cores report closed first-owner setup and reject anonymous
device reads with401. No old binary was started against a migrated schema.

## Correctness fix found during the protected rollout

The final cross-platform comparison initially stopped before any live SQL was
applied: PostgreSQL timestamp rows serialized differently on Windows and Linux.
JDBC's JVM-derived startup TimeZone can override `options` timezone settings.
The migration tool now executes `SET LOCAL TIME ZONE 'UTC'` inside every
repeatable-read snapshot transaction. This changes session serialization only,
not schema/data. It is covered by a real PostgreSQL regression comparing UTC and
Europe/Zurich JVMs, reproduced failing before the fix and passing afterward.

The old Windows Core was safely resumed on unchanged V39 while the complete suite
ran. Then a new maintenance boundary, fresh backup, restore and target-bound plan
were created. Older plans were retained, not modified to conceal their old tool
hash. The normalized final Windows/Linux table digests matched exactly.

Docker internal restore networks did not publish their database port on this
Desktop setup. Rather than granting the clones external egress, verification ran
in dedicated Python/JDK containers sharing only the isolated DB network namespace
and narrowly scoped recovery/artifact mounts. No application startup was used for
schema-only migration. A separate actual ARM64 Core/Web application drill used
only the restored, already-migrated Pi copy with real-provider/device egress
blocked and original backup keys mounted read-only; it passed before activation.

## Pi administrative scope and preservation

SSH did not have passwordless sudo, but the existing user already held Docker
administration. Narrow operator containers used that existing authority; no sudo,
group, ACL, authentication or host-package changes were made. Configuration
snapshots used read-only mounts and existing file-owner UIDs without capabilities.
The Gateway unit was paused/resumed through the standard system service-manager
bus using the existing administrative authority. No privileged container or host
namespace escape was needed.

The installed Compose file changed only Core/Web image references; canonical
validation retained all other service configuration. The operator used the exact
already-installed Docker/Compose binaries read-only, avoiding changed bind defaults
in a newer CLI. The root configuration update was hash-guarded and atomic.
Env, Caddyfile and all TLS bytes were verified unchanged. Only Core/Web were
recreated; PostgreSQL/Caddy container IDs and original data/key/Knowledge mounts
were retained. Pi-hole, Home Assistant, OTBR, Matter and radio services were not
restarted. Existing Gateway/Voice enrollment and destinations were preserved:
Gateway targets Pi loopback18080; Voice still targets guarded Windows Core8080.

Gateway heartbeat is fresh in the intended Pi Core. Both installations retain
three historical bindings with **zero grants**. Normal Gateway telemetry resumed,
but these legacy button actions remain denied until an eligible human explicitly
reviews and resaves each binding. No bulk resave, inferred OWNER approval or
physical/action test was performed. Cached/pending device work was not replayed.

## Actual verification and remaining acceptance

- Complete Core test/bootJar rerun: **449 recorded, zero failures/errors, one
  explicitly opt-in standalone live-provider smoke skipped**. Includes the new
  timezone regression and seven actual schema/restore cases. Source hashes stable;
  private manifest `.run/dev-recovery/schema-acceptance/a6dfb48c9c3c40619f29f14484182d8c/`.
- Existing reviewed Web262, Website40, lint/type/build evidence is retained;
  application source has not changed since those checks. Native Pi Web production
  build and actual restored-data Core/Web startup passed during this rollout.
- Operator unit checks: schema-tool13 and Gateway gate6 passed, Ruff clean.
  Original-data verifier compiled and exercised against actual original data,
  wrong-key negatives, and both live databases. Targeted formatting/diff checks
  cover the changed documentation; no general formatting rewrite.
- Four real production browser cases: Windows/Pi in DE/EN, normal TLS checking,
  loaded JS/CSS, local login form, closed first-owner setup, anonymous profile
  redirect and401 session endpoint; no JS errors or failed assets. No interception,
  ignored TLS errors, screenshots, trace, fabricated session or entered owner
  password. A password-authenticated production owner journey was **not** claimed.
- Existing Voice, Spotify receiver and media services are active; Gateway is
  active with fresh intended-Core heartbeat. Physical audio/actuator outcomes and
  live Google account writes were not tested by this rollout.

Remaining work is specific: owner review/resave of legacy bindings; controlled
physical/Voice and live calendar/family acceptance; owner password-login check;
productive central IdP/DNS/TLS/SMTP/lifecycle configuration; the scoped cloud
invitation extension. None is silently marked completed by healthy containers.
There is no SQL downgrade: if recovery is needed, keep post-upgrade data/audit and
effects, reconcile later revocations, restore into a separate target with original
keys/configuration, and choose a runtime matching that target's exact history.
Do not blindly restore old Gateway state, revive grants or launch V39/V41 against
V46. Retain the sealed original and current recovery evidence.
