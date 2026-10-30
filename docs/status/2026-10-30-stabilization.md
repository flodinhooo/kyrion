# Recovery integration and startup stabilization

Date: 2026-10-30. Scope: source integration, isolated verification and architecture
analysis. This session performed no production deployment, credential/configuration replacement, database
reset, Flyway repair or real Google/calendar/device write was performed.

## Source reconciliation

Primary development was `refresh/product-credibility` at `476972a`; recovery was
`fix/calendar-ha-recovery` at `547f0ae` with 62 changed/untracked recovery files.
The primary-only commits introduced public-website refinements, bounded Windows
recovery and Spotify output resolution. Those changes were retained. Recovery
application files did not overlap those implementation changes; README context
conflicted and was reconciled manually. Startup documentation preserves both
worktree configuration loading and the newer operator recovery workflow.

The original recovery worktree remains unchanged and uncommitted as a source
reference. Integration copies its reviewed changes into primary development;
it does not move/delete the worktree, rewrite history or stage its tracked gitlink.

Integrated behavior:

- Calendar range/calendar selection, timezone-safe editing, bilingual controls,
  explicit per-event synchronization, stable Google IDs, ETags, conservative
  conflicts, durable deletion/retry state and opt-in leased schedules.
- Google account verification, proactive/401 token refresh and visible revoked
  authorization. Direct edit/delete clients must supply calendar/version data.
- HA scheduled/on-demand/manual refresh, read-only light/contact observations,
  stable device identity, explicit cached-data diagnostics and stale Web snapshot
  protection. Zigbee execution retains its application-executor qualifier.
- Additive V32/V33 and upgrade/persistence regressions. V31 was restored to the
  historical SQL formatting/checksum `1755433543`, matching installed history.
  Its semantics were not changed and database checksums were not rewritten.
- Additional regression: permission revocation during a Calendar batch prevents
  subsequent event access. Already dispatched remote operations are not an atomic
  distributed transaction with RBAC/audit storage.

The original main README/status claimed Installer v1 was only planned, although
the bounded fresh-install scaffolding is already implemented. Installer pilot/
release, recovery and hardware acceptance still remain open. Historical status
files are evidence checkpoints, not the active priority order.

## Restore point and data safety

Before integration, source ZIP/patch/manifests were saved under ignored
`.run/stabilization/`. A custom PostgreSQL dump plus SHA-256 manifest lives under
its `private-backup/` directory. Existing restore tooling restored it into a
randomly named temporary database, checked successful V33 history and 37 public
tables, and removed only that verification database. The manifest records
`restoreVerified=true`. The real database was not restored/reset or altered by
that verification. This is SQL/source rollback evidence, not a complete verified
deployment backup of external accounts, keys, radios and operating systems.

This session did not overwrite private `.env`, key files or operator settings,
or replace the running helper's selected JAR with its newly built primary artifact.
Concurrent operator changes are documented below. Temporary tests use separate ports, an empty database,
separate key locations and disabled integration/sync schedulers.

## Startup findings and source fixes

The observed PostgreSQL process reported an interrupted previous run, synchronized
its Windows bind-mounted data directory and replayed WAL before accepting
connections. The observed interval was approximately five minutes. This was crash
recovery, not evidence that the database needed deletion or Flyway repair.
Compose's short health grace/`--wait` path failed before recovery completed, and
the helper nevertheless attempted Core. Core then exited because PostgreSQL was
still starting.

Recovery now starts Compose without recreating existing containers, polls an
actual SQL query for up to ten minutes and gates Core on readiness. Independent
optional services can still start after a database failure. The development
Compose template allows a longer startup grace and 120-second graceful stop.
These template changes were not applied to the existing container.

Previously an open port counted as success even while Ollama GPU discovery or
speech initialization was incomplete. Per-service HTTP body checks now gate
success. TTS has a fifteen-minute bound. A still-loading managed process is
reused after a timeout; the helper does not launch a duplicate model instance.
Existing external processes and WSL speech runtimes remain protected from restart.

Chatterbox previously called `from_pretrained` with online snapshot resolution
against `main`; its cold initialization exceeded the helper's five-minute limit.
It now loads an existing local snapshot with the exact required file set, or an
explicit local model directory. Missing artifacts never trigger a service-start
download. Startup phases have sanitized duration/error diagnostics. Background
initialization keeps `/live` reachable; `/ready` remains 503 until reference
conditioning and GPU warmup succeed. Transient I/O retries are bounded; permanent
configuration failures remain visible. CPU is an explicit runtime choice, not a
silent fallback. The existing batch speech contract is preserved.

Additional Compose/TTS lifecycle and CLI changes appeared concurrently in the
shared workspace during this review. They were preserved and reviewed as part
of the final source state, rather than overwritten or attributed to the original
recovery worktree. The CLI provides local status/start/log access to the same
operator helper; it does not grant Web host authority.

## Verification

- SQL backup/isolated restore: V33 successful, 37 public tables, original database
  unchanged by restore verification.
- Core: `gradlew.bat test bootJar --console=plain`, **218 tests**, zero failures,
  errors or skips. Includes Testcontainers HTTP/persistence, upgrade preservation,
  V31 checksum, Calendar conflicts/retries/leases/RBAC and HA observations.
- The first Core invocation could not find JDK 21. An isolated SHA-256-verified
  Temurin JDK 21 was provisioned under the ignored review directory; no project
  toolchain requirement or global Java installation was changed. A Kotlin daemon
  cache failure recovered using Gradle's non-daemon compiler fallback; final build
  succeeded. There is no configured Kotlin formatter/linter task.
- Web: **128 tests / 45 files**, ESLint, Next route type generation, TypeScript
  and production build passed. Build output used `.next-stabilization-build`,
  separate from the development server. Generated output stays ignored.
- AI: **122 pytest tests**, including local-only cache loading, failed warmup,
  loading/readiness HTTP behavior, bounded I/O retry and sanitized permanent
  failure. Ruff lint and format checks passed for changed runtime/tests. One
  third-party Starlette/httpx deprecation warning remains.
- Node: **8 tests**, covering delayed database recovery, permanent failure,
  delayed TTS/dead process/deadline, HTTP health validation, fixed operator
  actions/authentication and WSL/external-process preservation. Node syntax,
  Compose configuration and `git diff --check` passed.
- Two real isolated PostgreSQL/Core cold cycles on ports 15439/18080 reached
  `UP` with successful V33. They used a purpose-created container and empty
  ephemeral test data, separate Core configuration/keys, and no provider calls.
  Only the test process/container was removed afterward.
- An isolated real WSL/CUDA Chatterbox initialization completed from local cache
  in **108.8 seconds**, including reference conditioning and warmup, without
  replacing the running TTS process. A subsequent lifecycle fixture kept liveness
  available while loading, reached readiness in 31.1 seconds and produced a
  53,804-byte RIFF/WAVE response after 33.8 seconds. That invocation nevertheless
  ended with a nonzero tool-reported exit; a later retry overlapped the host
  interruption below. Functional output is established; clean process/host
  lifecycle acceptance is not.
- Read-only local health checks found PostgreSQL, Web, Core, AI, Ollama, Parakeet
  and Chatterbox reachable. These are the existing running processes, not evidence
  that the new helper/runtime source has been deployed.

## Remaining acceptance and risks

No full Windows shutdown/reboot, Docker/WSL shutdown, Pi reboot/network outage,
new-runtime rollout, authenticated Calendar browser acceptance or real Google
write acceptance was performed. A complete host cold start of the **new** source
cannot be claimed from isolated checks. Keep this as an explicit acceptance gate.
Do not replace the working installation solely to make that claim under a
no-deployment instruction.

During final verification, WSL/Docker was observed restarting and local Web/Core/
STT/TTS/SQL probes temporarily failed after having passed. PostgreSQL re-entered
crash recovery. There is insufficient evidence to attribute this to interpreter
teardown, host/driver behavior or concurrent operator activity. Windows memory and
fresh WSL memory observations did not establish memory exhaustion. Do not report
this as a solved host lifecycle problem or a currently all-green cold start.

There is independent evidence of concurrent activity: source additions, recovery
start audit entries not issued by this session, and a changed private operator
`coreJar` selection. This session did not change that selection. Further lifecycle
mutations were stopped to avoid interfering with the other operator. Read-only
probes and source validation remain separate from that shared runtime state.

The known host problem where terminating speech processes disrupted WSL/Docker
was not reproduced through destructive termination. Its underlying cause remains
unresolved; the helper preserves WSL runtimes. Disk cache, GPU/VRAM contention,
private reference audio and pre-provisioned weights remain startup dependencies.

Calendar/HA retain bounded scope: remote success plus audit failure still needs
reconciliation; global synchronization/token locks can serialize accounts;
provider calls inside HA's owner transaction can delay other owner operations;
legacy clients may omit Calendar revision preconditions. Physical/provider
acceptance and license/release gates remain separate. See the
[AI architecture review](2026-10-30-ai-architecture-review.md) for model/provider
coupling, deadline/context debt and the proposed staged multi-provider plan.
