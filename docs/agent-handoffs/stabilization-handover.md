# Stabilization agent handover

Date: 2026-10-30. Owner: Windows runtime, integration acceptance, Pi/Core network
and existing Voice infrastructure. This is this agent's independent handover.
Finalization is documentation-only: no new feature, runtime restart, migration,
deployment, paid request or full regression rerun was performed for this handover.

## Assignment and ownership

The assignments covered recovery/TTS/startup stabilization, WSL/Docker diagnosis,
live integration/demo checks, Google synchronization verification, Pi/Core
connectivity, and finally approval-gated LAN access while protecting Pi-hole.
Sprint 01's integrated Calendar/HA recovery, initial working GPU Chatterbox,
seven ready services and 546 tests were supplied as baseline for the later
sprints. Do not count that entire baseline or other agents' recovery commits as
new implementations by this agent.

This agent implemented the later operator/recovery improvements, Calendar proxy
fixes, diagnostics, smoke/acceptance tooling and scoped LAN activation described
below. K-AI providers/routing, agents, memory/context, Velora 2.0, Spaces and
K-Data/Knowledge are other agents' work. Running their tests is not authorship.
No new branch/worktree was created by this agent; existing dirty worktrees were
left intact. No database migration was authored or altered by this agent.

## Existing evidence and how to read it

- [Sprint 02](../status/2026-10-30-stabilization-sprint-02.md): operator workflow,
  WSL timeline, local Calendar fix, live HA/browser checks and build evidence.
- [Sprint 03](../status/2026-10-30-stabilization-sprint-03.md): Google reauthorization
  clarification, real Google CRUD, direct GET fix and original LAN diagnosis.
- [Sprint 04](../status/2026-10-30-stabilization-sprint-04.md): explicit approval,
  effective firewall boundary, actual activation, Voice tests and remaining limits.
- [Startup](../development-startup.md), [demo checklist](../demo-readiness-2026-10-31.md),
  [Voice/manual acceptance](../pi-core-and-voice-acceptance.md),
  [Calendar synchronization](../calendar-synchronization.md).

Historical pending OAuth/LAN statements are superseded by Sprint 03/04 evidence.
The user had already reauthorized Google; no further OAuth was needed. The
Pi/Core procedure retains obsolete activation examples under its supersession
banner: **do not use the old `Set-CoreLan.ps1 -Apply` path**, which is blocked.
Prior test counts are separate evolving-source checkpoints, not additive totals
or certification of today's combined four-agent HEAD.

## Implemented components and changed behavior

| Component | This agent's change | Completion / evidence |
|---|---|---|
| Existing `infrastructure/dev-stack.mjs` and recovery helpers | Idempotent starts join active jobs or use bounded cooldown retry; explicit scoped restarts preserve external processes, WSL and untargeted/Pi services; failed spawns no longer masquerade as loading processes | Implemented and tested; source helper v5 checked in isolation; the existing active helper was not restarted merely to load new source |
| PostgreSQL operator restart/readiness | Explicit graceful 120-second stop of existing container, SQL readiness, bounded Core reconnect; no volume deletion/reset | Two real controlled cycles, corrected transient reconnect false failure, retained data and other Docker workloads |
| `dev-readiness.mjs`, `dev-command.mjs`, `dev-diagnostics.mjs`, `dev-soak.mjs` | Bounded Docker commands, distinct HTTP/loading/failure/timeout states, sanitized Windows/WSL/GPU/container metadata, retained outage samples | Implemented/unit-tested; real diagnostic/short-soak results include failures rather than hiding them |
| Web local Calendar DELETE proxy | Successful empty Core HTTP200/204 becomes empty204 instead of JSON parsing producing false503 | Regression tests and real marked local-event CRUD passed; auth/CSRF/revisions retained |
| Web direct Google event GET proxy | Allowlist-forward `calendarId`, `start`, `end`, preserve offset encoding, no cached reads | Four route regressions and real secondary/range-aware provider smoke checks |
| `demo-smoke.mjs`, `demo-google.mjs` and tests | Public/authenticated demo acceptance; opt-in marked-event local/Google writes; strict ownership/ETag cleanup guards | Real browser/readiness/Calendar/HA observations; physical actuator success is not claimed |
| `Prepare-CoreLan.ps1`, `Install-CoreLanGuards.ps1`, `Invoke-CoreLanGuardsAdmin.ps1`, `core-lan-guard-addresses.json` | Configuration backup/plan, narrowly scoped UAC entry, two persistent Block guards, CIDR-to-Windows-mask normalization | Actually installed and verified in ActiveStore; real allowed-Pi/denied-WSL canary before restart |
| `Verify-CoreRuntime.py` and six tests | Read-only installed Flyway checksum/pending migration/sync lease gate against selected JAR | 33 installed migrations matched at actual activation and final verification; rejects mismatches/new migrations/active leases |
| `Activate-CoreLan.ps1` | Verify scope/PID/artifact, preserve identical JAR, restart only Core with dedicated Java21, wait for localhost/Pi/all-local readiness, rollback startup on failure | Actual activation succeeded; final process-only implementation is committed through `641e6fe`; failure rollback not deliberately exercised |
| `Probe-PiCore.ps1`, `Probe-VoiceSession.py`, `Probe-VoiceTurn.py` | Pinned SSH network/auth checks, real session/greeting validation/cleanup, opt-in process-local IPv4 diagnostic, synthetic stop turn without capture/playback/device execution | Real session and synthetic STT/Core/TTS round trip passed; six operator-probe regression tests across the two Voice test files |

Relevant Web files are
`apps/web/src/app/api/calendar/events/[id]/route.ts` (DELETE) and
`apps/web/src/app/api/integrations/google/calendar/events/route.ts` (GET), with
their route tests. These paths were verified during documentation closeout.
The existing Core APIs were not replaced or extended by these proxy corrections.

## Architecture, interfaces and data ownership

Windows runs native Core JVM8080, Web3000, AI8000, Ollama11434, STT8040 and
TTS8020; Compose publishes PostgreSQL5432 on loopback. Core LAN repair does not
require Docker publishing, WSL NAT, DNS or router changes. Core remains the
authoritative authentication/RBAC/business/persistence boundary. The AI/STT/TTS
services and Pi clients use existing HTTP contracts; no provider-routing,
Space/tenant isolation or memory/context behavior was implemented here.

Web proxy requests keep server-side sessions/credentials and CSRF for mutations.
Google live checks use the normal dedicated authenticated browser context, not
extracted bearer caches. Test cleanup requires generated ID, marker, description,
ETag and nonrecurring scope; no actor-wide sync or personal-event mutation.
Google stable IDs, conditional ETags/409 and offset instants were checked through
the existing integration. Genuine Samsung-origin edits of linked local replicas
and large live pagination were not tested.

Voice flow checked: installed Pi client -> authenticated Core session/turn ->
existing AI/STT transcription -> deterministic stop response -> existing TTS ->
WAV back to Pi memory. Existing routes include `/v1/voice-satellite/sessions`,
`/.../{sessionId}/greeting`, `/.../{sessionId}/turns` and
`/v1/voice-satellite/sessions/close`. Existing satellite/gateway Bearer enrollment
credentials remain protected. The operator stop probe refuses `/execute` and
`/playback-completed`; it does not pretend in-memory validation was audio playback.
An expected404 on closing an already server-closed explicit-stop session is
handled only after successful stop completion; an auth failure is not accepted.

No new database tables/migrations were added. Existing `flyway_schema_history`
and `calendar_sync_schedule` are read for the startup gate; `gateway_node` and
`voice_dialogue_session` supplied sanitized acceptance counts. The running JAR
contains V1–V33. V34–V37 in current source are parallel AI/context/Knowledge work,
not changes applied by this activation. **Do not deploy the newest build or
repair Flyway history merely to reproduce this agent's LAN result.**

## Security boundary and last verified runtime

Last live verification was October 30 around 21:47 Europe/Zurich, before this
documentation-only closeout. No fresh runtime claim is inferred from Git status.

- Windows Private Ethernet `192.168.1.107`; Pi route source `.116`. Existing
  Allow: Private/inbound TCP8080, sources `.115` and `.116` only.
- A separate broad JDK22 Allow would bypass that narrow Allow. Existing rules
  were not edited. Core now uses the dedicated executable
  `.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1/bin/java.exe`.
- Persistent `Kyrion-CoreLan-Guard-NonPi-v1`: that executable/TCP8080 only,
  all profiles, all IPv4 except127/8 and the two Pi addresses, plus all IPv6.
  `Kyrion-CoreLan-Guard-NonPrivate-v1`: same executable/port, all sources in
  Public/Domain. Explicit Block precedence prevents broad Allow bypass.
- IPv6 `::/0` was rejected by Windows; equivalent `::/1` + `8000::/1` works.
  IPv4 CIDRs read back as dotted masks. Tests prove exact full address coverage.
- Before Core interruption a nonce-only HTTP canary used the same executable and
  LAN TCP8080: Pi `.116` succeeded, WSL `172.21.146.86` timed out, localhost Core
  stayed healthy. Canary was stopped; denied WSL access was repeated afterward.
  `.115` is scope-verified, not a separately exercised live source. This is not
  a physical test from every LAN device or an external network penetration test.
- Only identified original Core parent PID38276 and verified children stopped.
  Last accepted Core PID35108 is ephemeral; always re-identify it. Immutable JAR
  SHA256: `B592336BACFD047DEDF8536D07973626B1F7A465C64B4FF8BB0D70915EB577F9`.
- Bind `KYRION_CORE_ADDRESS=0.0.0.0` is **process-only**. An initially appended
  shared override was removed after noticing generic recovery could select
  unguarded JDK22. Final `.env` hash equaled its pre-activation backup exactly.
  A normal later Core start therefore falls back safely to loopback, losing LAN
  connectivity until the guarded startup path is deliberately selected.
- Allowed Pi peers can reach all HTTP endpoints on the Core listener, not just
  Voice; existing endpoint authentication/authorization still applies. Local
  HTTP is not TLS encryption. No extra WebSocket port was published.
- Pi-hole/port53/DHCP/router/DNS/IPs and all Pi service configurations were left
  unchanged. After-check: Pi-hole Docker start time still October22, TCP/UDP53
  listening, external DNS working. Router resolver resolves the Core hostname;
  direct Pi-hole queries return NXDOMAIN, unchanged from before activation.

## Operations and configuration

Read-only commands for the next operator:

```powershell
node infrastructure/dev-stack.mjs status
node infrastructure/dev-stack.mjs diagnose
node infrastructure/demo-smoke.mjs
& infrastructure/dev/Probe-PiCore.ps1
python infrastructure/dev/Verify-CoreRuntime.py <reviewed-running-jar>
```

`dev-stack.mjs start` is the existing general workflow, but can affect configured
Pi units and **does not currently guarantee guarded LAN persistence**. Do not run
it reflexively during a Pi-hole-protected maintenance window. Do not invoke broad
`restart --confirm` to repair a single listener.

`Activate-CoreLan.ps1 -CoreProcessId <fresh-pid>` is a dry review; `-Apply` is a
deliberate Core-only interruption after effective guards and migration/lease
checks. Its local rollback starts the same original artifact with explicit
loopback. Preserve the final process-only fix from `641e6fe` during integration.
Never globally set LAN bind in `infrastructure/.env` with the generic helper.

Normal credentials/configuration remain in existing protected local files:
`infrastructure/.env`, `.run/dev-recovery/settings.json`, the operator key,
pinned SSH identity and installed satellite/gateway credential files. This
handover contains no credential values. `.run/dev-recovery/sprint04` holds private
backups/manifests/probe evidence: backups contain secrets and must not be shared.
Keep that directory/runtime artifact until an independently checked replacement
and rollback exist. Recheck DHCP/DNS addresses and firewall source scope later;
do not change Pi/Windows static addresses or Pi-hole to fit stale documentation.

## Verification record

These are already executed results, not reruns during documentation closeout.

| Checkpoint | Commands / scope | Result |
|---|---|---|
| Sprint02 | Core Gradle `test bootJar`; Web Vitest, ESLint, `pnpm exec tsc --noEmit`, Next build; full AI | Core222; Web145/48 files; AI163; builds/typecheck/lint passed on that checked source |
| Sprint03 | Same suites; isolated JDK21/output to avoid parallel build collisions | Core233; Web149/49 files; AI164; all corresponding builds/typecheck/lint passed |
| Sprint03 speech | Targeted AI TTS/speech tests and Ruff | 18 passed; existing Velora voice retained |
| Final Sprint04 | `node --test infrastructure/dev-*.test.mjs infrastructure/demo-*.test.mjs` | 34 passed |
| Final Sprint04 | From `services/voice-satellite`: `../ai/.venv/Scripts/python.exe -m pytest -q` | 56 passed; existing AI venv reused because no satellite Windows venv existed |
| Final Sprint04 | From `services/gateway-agent`: same pytest executable | 17 passed, one Linux-metrics test skipped on Windows |
| Final Sprint04 | `services/ai/.venv/Scripts/python.exe -m pytest infrastructure/dev/test_verify_core_runtime.py -q` | Six migration-gate tests passed |
| Final Sprint04 | Targeted Ruff check/format for operator probes/tests/runtime gate; PowerShell parser tests; `git diff --check` | Passed after fixes |
| Final Sprint04 | `docker compose --env-file infrastructure/.env -f infrastructure/compose.yml config --quiet` | Passed, no config/secret dump |
| Final runtime | `dev-stack.mjs status`, public `demo-smoke.mjs`, Pi probe and real Voice probes | Seven services ready; eight public-smoke checks passed; auth greeting and synthetic stop round trip passed |

Earlier Gradle commands used JDK21, `--no-daemon --max-workers=2`, in-process
Kotlin compilation and an ignored Gradle init script redirecting build output.
Next build used `KYRION_BUILD_DIRECTORY=.next-sprint02-build`. See the dated
reports for full checkpoint commands. No new Core/Web/AI full suite/build was
claimed after the later four-agent source changes.

### Failures, corrections and non-verifications

- Five-minute Sprint02 soak:30 samples, one failed Core probe; later two-minute
  soak13/13 passed. Sprint03 two-minute soak:13 samples, one 2007ms Core timeout.
  Boot/container identity did not change during those timeouts. Overnight
  stability is unproven; failures remain recorded.
- Shared WSL reset: Docker bootstrap/proxy exit1 with `0x80072746` at17:43:26UTC,
  engine recovery17:44:50, PostgreSQL WAL ready17:47:57. Initiating cause unknown;
  no proven OOM/GPU correlation. No speculative resource-limit changes made.
- Initial Core Testcontainers startup/log-wait failure subsequently passed on
  full rerun without hiding it with timeout changes. Parallel AI cancellation
  test and chat/settings build/lint failures were corrected by that other agent;
  final suites passed. Those are not fixes authored by this stabilization agent.
- Initial real Calendar DELETE returned false503: fixed and live reverified.
  Historical Google409 requiring reauthorization was superseded by the user's
  reauthorization and seven passing marked Google CRUD/readback/cleanup checks.
- Original broad LAN attempt was auto-review-rejected before execution in
  Sprint03; Sprint04 obtained explicit authorization for the actual change.
  Initial firewall installs failed on permissions/address representation/scope
  normalization; successful UAC installation and strict effective checks followed.
- First synthetic stop probe reported cleanup failure because Core had already
  closed the session; bounded expected404 handling was added/tested, then the
  real probe fully passed. Other auth errors still fail.
- Default hostname Voice probe eventually passed but waited minutes on router
  IPv6 records. Diagnostic IPv4-only process passed in about2–3 seconds; this
  did not repair or redeploy installed clients.
- Gateway unit/journal success is not Windows-Core acceptance: DB heartbeat is
  stale. Its root-owned config cannot be read by the available account; `sudo -n`
  requires a password. No credential extraction/permission widening was used.
- No physical wake-word/microphone/speaker/actuator acceptance, Samsung-origin
  linked-replica edit, large live pagination, cloud-provider paid test, Windows
  reboot or deliberate post-activation failure/rollback drill was performed.

## Git and cross-agent integration

At first closeout inspection HEAD was `37ba511`; while this document was being
written another process committed the outstanding stabilization files in
`641e6fe`. These observations are not a frozen release. Relevant commits
containing this agent's files include `1033fc2`
(scoped recovery), `7d17aab` (Calendar DELETE tests), `347234e` (Google smoke and
Windows diagnostics), `4217ee2` (firewall/runtime gate) and `74b2f66` (activation/
Voice probe baseline). Some are mixed commits assembled by another process.
Do not attribute their other AI/Knowledge content here or cherry-pick them
wholesale without inspection. Google route history also crosses mixed commits.

**Initially uncommitted, subsequently committed in `641e6fe`:**
`infrastructure/.env.example`, `infrastructure/dev-core-lan.test.mjs`,
`infrastructure/dev/Activate-CoreLan.ps1`, `Probe-VoiceSession.py`,
`Probe-VoiceTurn.py`, `Verify-CoreRuntime.py`; untracked
`infrastructure/dev/test_verify_core_runtime.py` and
`services/voice-satellite/tests/test_operator_turn_probe.py`.
These include important security/process-scope corrections beyond the older
baseline, not disposable experiments. Another process committed them; this
documentation agent did not stage or commit application code. Preserve that
commit's corrections, rather than replaying only its older predecessors.

The same commit also captured the previously modified own startup, demo,
Pi/Core, status-index and Sprint04 documentation. They are not bundled into this
new handover's commit, minimizing shared-file races. Dirty
`.worktrees/calendar-ha-recovery` and `.worktrees/kyrion-spaces` belong to existing
parallel work and were not reset, moved or committed here. The index was empty
when inspected. Final main-checkout status before this handover's commit had only
this untracked handover and the two dirty existing worktrees. Only this new
handover is intended for this agent's closeout commit;
inspect `git log -1 -- docs/agent-handoffs/stabilization-handover.md` for its hash.

Resolved during closeout, **STAB-012**: the initially uncommitted security
corrections and their tests are now recorded in `641e6fe`. Verification of Git
status/history confirmed inclusion. This source-preservation gate is closed;
joint source/runtime acceptance remains STAB-006, not inferred from a commit.

Shared boundaries requiring coordination:

- K-AI/Velora changes share Core `application.yml`, authentication/Voice routes,
  AI speech contracts, Web chat and build artifacts. Preserve operator guards,
  existing authenticated Voice compatibility and the selected known-good JAR.
- K-Data/context changes add migrations V34–V37 and affect Core startup/speech
  response behavior. Their validation is recorded in the other handoffs, not
  inferred from this agent's older233-test build or live V33 artifact.
- Spaces introduces separate isolation/API changes; Calendar/HA/Voice service
  credentials must not bypass any eventual workspace ownership checks. No new
  Spaces-aware behavior was implemented or jointly accepted here.
- Integrate in order: preserve security corrections; freeze/review combined
   source and migrations; prove database compatibility and contracts; build/test;
  obtain the appropriate runtime-change approval; then run real LAN/integration
  acceptance. Never update Flyway history to make a newer binary start.

Other agents' independent records: [K-AI/Velora](kai-velora-handover.md) and
[K-Data](kdata-handover.md). A Spaces handoff was not present at inspection;
do not invent its filename or edit another agent's handoff.

## Current State

1. **Proven at last runtime check:** seven local services; protected Pi/Core
   access, unauthenticated denial, valid authenticated greeting and synthetic
   STT/Core/TTS turn; unchanged functioning Pi-hole; local/Google marked-event
   CRUD and HA import/refresh at earlier checkpoints; public/browser API/UI
   checks as specifically recorded.
2. **Implemented but incompletely validated:** activation failure rollback,
   scope across future startup paths, extended recovery/soak behavior and latest
   four-agent integration. Final implementation is committed through `641e6fe`,
   but the combined source is not jointly runtime-accepted.
3. **Not working reliably/proven:** prompt hostname Voice startup (IPv6 delays),
   fresh Gateway association to this Windows Core, LAN persistence through
   ordinary future Core restart, full acoustic/hardware demo and Windows cold boot.
4. **Risks:** replaying the pre-correction activation can persist unsafe global
   bind; changing Java path invalidates program-scoped protection; newer artifacts
   may apply other agents' migrations; WSL reset cause remains unknown. Current
   protected running process is not a deployable, reproducible frozen release.
5. **First next-start checks:** read this record/current Git diff; preserve
   process-only patches from `641e6fe`; inspect PID/JAR/Java/guards and config without printing secrets;
   check all service readiness and Pi/DNS; do not assume historic IP/PID/HEAD.

## Open TODOs

Eleven open items: **zero P0, six P1, five P2**. No item is closed merely because
a helper or fixture exists. STAB-012's source-preservation gate was resolved by
the intervening commit as recorded above; there is no newly verified active
security exposure being claimed.

### STAB-001 — Guarded LAN startup persistence

- **Priority:** P1. **Components:** recovery helper/CLI, Java selection, firewall.
- **Problem/current state:** current LAN works only in the verified process;
  ordinary later Core starts safely return to loopback.
- **Next steps:** integrate explicit opt-in dedicated runtime selection and
  effective guard checks into the existing workflow; fail closed on missing or
  mismatched guards; preserve operator auth and Core-only restart boundaries.
- **Dependencies:** preserve `641e6fe`, agreed combined runtime artifact, no Pi changes.
- **Acceptance:** repeat start/restart/cold-start preserves only authorized Pi
  access, localhost readiness and other services; missing guards refuse LAN.
- **Risks:** inherited `JAVA_HOME`, global `.env`, or changed executable bypassing
  program-scoped firewall; old helper still loaded until deliberately replaced.

### STAB-002 — Bounded IPv4/IPv6 client fallback

- **Priority:** P1. **Components:** installed Voice/Gateway HTTP clients, DNS use.
- **Problem/current state:** router AAAA answers cause minutes of retries; an
  isolated IPv4 diagnostic is fast, but production clients were not changed.
- **Next steps:** implement/test bounded address-family fallback within existing
  clients, retaining hostname/DHCP discovery and credentials; separately authorize
  installation on Pi without modifying Pi-hole or unrelated units.
- **Dependencies:** networking policy from STAB-001; coordinated Pi maintenance.
- **Acceptance:** normal configured hostname authenticates promptly, reconnects
  after transient failure, and handles IPv4/IPv6-only/dual-stack fixtures.
- **Risks:** hardcoded IP drift, global resolver monkeypatching, DNS disruption.

### STAB-003 — Identify Gateway's actual Core target

- **Priority:** P1. **Components:** Pi system Gateway, protected config, Core DB.
- **Problem/current state:** unit logs report successful heartbeats, while the
  checked Windows Core has no fresh heartbeat; root config access is unavailable.
- **Next steps:** authorized administrator reads only target URL/identity metadata,
  compares the intended Core, then separately approves any necessary correction.
- **Dependencies:** privileged read-only Pi access; STAB-002 if same IPv6 delay.
- **Acceptance:** newly authenticated heartbeat from that exact Pi advances the
  intended Windows Core gateway row and appears correctly in UI; no secret output.
- **Risks:** targeting another installation or changing a working gateway blindly.

### STAB-004 — Establish WSL/Docker interruption root cause

- **Priority:** P1. **Components:** Windows/WSL/Docker/GPU/PostgreSQL.
- **Problem/current state:** shared VM reset with0x80072746 is evidenced; initiating
  cause is unknown and neither GPU nor OOM is proven.
- **Next steps:** retain sanitized diagnostics across a recurrence, correlate
  outer event timestamps/boot IDs/container starts, then propose evidence-based fix.
- **Dependencies:** available Windows event access and coordinated observation.
- **Acceptance:** supported cause/fix or reproducible bounded failure evidence;
  extended monitoring without silent resets/data loss; no speculative limit edits.
- **Risks:** shared Docker workloads and productive Pi DNS; log privacy.

### STAB-005 — Coordinated Windows cold-start acceptance

- **Priority:** P1. **Components:** host, Docker, all local services, operator CLI.
- **Problem/current state:** full host reboot was not authorized/performed.
- **Next steps:** finish guarded startup, arrange explicit reboot approval and
  data-safe shutdown, then follow readiness/SQL/Pi/DNS acceptance after boot.
- **Dependencies:** STAB-001/004, user approval, known-good runtime artifact.
- **Acceptance:** one reproducible workflow restores required services with correct
  scope/authentication, preserves DB data and does not restart/reconfigure Pi-hole.
- **Risks:** unclean PostgreSQL recovery, helper autostart drift, unrelated workloads.

### STAB-006 — Freeze and jointly validate the four-agent integration

- **Priority:** P1. **Components:** Core/Web/AI, contracts, migrations, Spaces/K-Data.
- **Problem/current state:** passing build checkpoints precede later parallel source;
  live artifact remains V33 while source contains V34–V37.
- **Next steps:** reconcile handoffs and own diffs, review migration ordering,
  isolation/auth/Voice contracts, freeze a candidate and run required suites before
  any deliberate runtime replacement.
- **Dependencies:** all agents' handoffs and preserved final corrections; appropriate migration review.
- **Acceptance:** one identified source/artifact/database state passes builds,
  migrations, isolation and actual integration checks; rollback constraints clear.
- **Risks:** mixed commits, shared output overwrite, irreversible migration effects.

### STAB-007 — Physical Voice and playback acceptance

- **Priority:** P2. **Components:** wake detector, microphone, ALSA/PipeWire/Bluetooth.
- **Problem/current state:** model/silence and synthetic/API paths pass; real wake
  recall, capture and audible output remain unaccepted.
- **Next steps:** after fallback repair, user checks intended sink/mute, says the
  wake phrase and a harmless request, hears reply, stops/repeats; record timestamps.
- **Dependencies:** STAB-002/003; physical user participation, no forced volume.
- **Acceptance:** reproducible microphone-to-speaker flow and clean repeated sessions.
- **Risks:** wrong output, private recordings, mistaking valid WAV for audible sound.

### STAB-008 — Complete Google external-origin/large-calendar acceptance

- **Priority:** P2. **Components:** Calendar integration, provider sync, Web status.
- **Problem/current state:** live marked CRUD/ETag/timezone checks and user-confirmed
  Samsung delivery pass; external-origin linked edits and >100 live events untested.
- **Next steps:** use only separately marked objects to test external edits and
  conflict/status behavior; use existing fixtures for scale unless a safe test
  calendar is explicitly available. Do not reauthorize healthy OAuth unnecessarily.
- **Dependencies:** valid existing integration, calendar ownership/selection.
- **Acceptance:** no duplicate IDs, correct timezone/status/conflict handling and
  cleanup; clearly distinguish range readback from bidirectional replica sync.
- **Risks:** personal-event mutation, global sync side effects, provider throttling.

### STAB-009 — Physical integration/demo gates

- **Priority:** P2. **Components:** HA/Zigbee/Nanoleaf/Spotify/Lounge/Media Player.
- **Problem/current state:** inventory/UI/API/status checks exist, no complete
  actuator or audible media demonstration was conducted.
- **Next steps:** select non-disruptive authorized devices/media, verify actual
  results and reconnect behavior, retain precise API-versus-physical evidence.
- **Dependencies:** STAB-003/006, credentials/hardware, physical-action approval.
- **Acceptance:** demonstrated allowed flows with correct ownership/RBAC and real
  device/player outcome; unavailable hardware explicitly recorded.
- **Risks:** unintended home actions, playback disturbance, confusing active units
  or successful page loads with successful physical integrations.

### STAB-010 — Investigate isolated Core probe latency and extended uptime

- **Priority:** P2. **Components:** Core, DB pool, diagnostics/soak.
- **Problem/current state:** short observations include isolated Core timeouts with
  unchanged WSL/DB identities; no overnight reliability evidence.
- **Next steps:** correlate probe latency, pool/JVM/load metadata and longer bounded
  observation on a frozen candidate; fix a supported cause rather than hiding it.
- **Dependencies:** STAB-004/006; observation time and retained sanitized metadata.
- **Acceptance:** explain timeout cause and retain truthful failure accounting;
  agreed extended-duration readiness/recovery acceptance passes.
- **Risks:** flattening transient failures into an all-green final status.

### STAB-011 — Exercise activation rollback and startup failure guards

- **Priority:** P2. **Components:** PowerShell activation, immutable artifacts/backup.
- **Problem/current state:** success path exercised; deliberate startup/Pi/security
  failure and rollback scenarios were not run on the shared live stack.
- **Next steps:** add proportionate isolated tests for each failure stage, then
  coordinate a narrowly scoped real rollback drill only if needed/approved.
- **Dependencies:** final corrected source and STAB-001, isolated test ports/process fixtures.
- **Acceptance:** only identified Core stops, same artifact restores loopback,
  no shared config overwrite, failed guard verification never opens LAN, critical
  failure is surfaced; existing firewall/Pi/data remain intact.
- **Risks:** accidentally exercising destructive process paths against real PIDs;
  guard rules should only be removed after verified loopback restoration.

## Recommended Next Steps

1. **P1:** make guarded LAN startup reproducible and bound client address-family
   fallback (STAB-001/002); coordinate any separately authorized Pi deployment.
2. **P1:** identify Gateway target through privileged read-only inspection and
   freeze/validate the combined four-agent candidate (STAB-003/006).
3. **P1:** correlate WSL failures, then coordinate cold-start/extended observation
   rather than restarting shared infrastructure speculatively (STAB-004/005/010).
4. **P2:** complete physical Voice/device and external Calendar acceptance using
   marked test data and explicit hardware-action boundaries (STAB-007/008/009).
5. **P2:** exercise isolated rollback/failure guards before the next planned
   runtime replacement (STAB-011); preserve `641e6fe`'s process-only protection.

No further implementation is started in this session.
