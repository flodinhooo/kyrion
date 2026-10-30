# Stabilization sprint 01: final local runtime verification

Date: 2026-10-30, final checks approximately 18:53 Europe/Zurich.
This supplements [source integration and concurrent runtime evidence](2026-10-30-stabilization.md).
Earlier interrupted or partially ready probes in that report remain historical
evidence; the later observations below do not establish a reliable Windows reboot.

## Implemented and preserved

- Reconciled the recovery source against the primary checkout. The recovery
  branch is already an ancestor; Calendar/HA implementation and regression files
  are present. Concurrent commits `3661544` and `fe73e68` integrated/reported the
  shared work. No additional branch/worktree was created or recovery worktree
  modified by this verification.
- The existing helper gates Core on an actual database query, waits up to ten
  minutes for recovery and fifteen minutes for TTS, and checks HTTP response
  bodies. Compose now permits five minutes startup grace and a 120-second stop;
  existing containers were preserved rather than recreated to apply the template.
- Chatterbox loads provisioned local weights without network downloads, preserves
  the existing Velora reference and exposes background initialization stages,
  `/live`, `/ready` and compatible `/health`. Readiness requires conditioning and
  warmup. Local transient I/O retries are bounded; permanent failures stay visible.
  CPU is an explicit diagnostic option; CUDA remains the active default.
- `dev-stack.mjs` reuses the existing bounded helper for start/restart and provides
  HTTP/SQL status plus per-service logs. Web readiness probes the independent
  recovery page, so an unavailable Core does not make Web itself appear down.
  `dev-command.mjs` bounds even a hung Docker client's status check; it terminates
  only that client, never the container or WSL process tree. Three regressions
  exercise this failure mode, nonzero exit and missing Docker.
- All 33 installed SQL migration checksums were compared to the freshly tested
  primary-checkout JAR: zero mismatches and all installed migrations successful.
  Private local `settings.json` now selects that primary JAR under
  `.run/dev-recovery/core-build/libs/` for the next helper launch. This verification
  did make that bounded operator-setting change; older concurrent reports describe
  their own actions. No Flyway repair, history rewrite or data reset was performed.

## Automated verification

| Check                                       | Result                                                  |
|---------------------------------------------|---------------------------------------------------------|
| Core Gradle tests                           | 218 tests, 43 suites; zero failures/errors/skips        |
| Core `bootJar`                              | Passed using isolated JDK 21 and separate build output  |
| Web Vitest                                  | 128 tests, 45 files passed                              |
| Web ESLint / TypeScript                     | Passed                                                  |
| Next production build                       | Passed using `.next-stabilization-build`                |
| Python service tests                        | 122 passed; one upstream TestClient deprecation warning |
| Voice Satellite Python tests                | 50 passed                                               |
| Gateway Python tests                        | 17 passed, 1 skipped (platform-specific check)          |
| Changed TTS Python Ruff lint / format check | Passed                                                  |
| Node readiness / policy / CLI-client tests  | 11 passed                                               |
| Compose config / Node syntax / whitespace   | Passed                                                  |

The initial Core attempts failed for missing JDK 21 and competing Kotlin build
outputs. The successful rerun used an isolated Microsoft JDK 21, separate output,
two workers and in-process non-incremental compilation. Global Java configuration
and the project toolchain requirement were preserved. The original Web lint run
included generated build output and failed; after its exclusion, lint passed.

## Real runtime evidence

- Final `node infrastructure/dev-stack.mjs status` exited successfully with
  PostgreSQL, Web, Core, AI, Ollama, STT and TTS ready. SQL `SELECT 1` was executed.
- Idempotent CLI startup passed. A subsequent recovery job
  `096e36ba-8280-4746-a19e-b06637d62411` restored missing speech services after a
  shared WSL/Docker interruption. No database volume was removed or reinitialized.
- Updated GPU Chatterbox startup logged ready after 52.9 seconds. `/live`, `/ready`
  and `/health` returned 200 with ready state. Two direct synthesis calls returned
  200 `audio/wav`: mono, 24 kHz; 117164 and 76844 bytes, with 2.44 and 1.60 seconds
  audio, generated in 4.44 and 3.44 seconds respectively.
- The unchanged AI `/v1/speech/synthesize` endpoint also returned 200 `audio/wav`,
  mono 24 kHz, 56640 frames, in 5.02 seconds. This checks the existing AI-to-TTS
  boundary, not authenticated Core/Satellite/speaker end-to-end acceptance.
- An isolated CPU HTTP probe observed `/live` 200 while `/ready` was 503, then
  readiness after 279.75 seconds during host recovery. Two actual mono 24 kHz WAVs
  were generated in 24.32 and 20.03 seconds; the temporary HTTP server stopped.
  Its first attempt was interrupted by the shared host incident. The second run
  reached both audio checks and shutdown but its PowerShell stderr-redirection
  wrapper returned exit 1; it is not counted as an automatically passing command.
- Pinned-key SSH reported Spotify receiver, Voice Satellite, media player and
  gateway services active. No Pi configuration was changed. Voice Satellite
  reported two restarts; this alone does not identify their cause.

## Remaining limits and next work

1. Diagnose the recurring shared WSL/Docker interruption using host/driver/kernel
   evidence. Memory exhaustion was not established. No global WSL shutdown or
   unrelated Docker-service restart was used here. More than one operator was
   active, so causation cannot be assigned to the isolated TTS test.
2. Validate a coordinated Windows reboot/full stopped-state start and clean
   shutdown, including other local Docker workloads. The currently green snapshot
   does not prove unattended reboot reliability.
3. Complete signed-in Google/HA acceptance using disposable test events and
   authorized hardware. Fixtures cover pagination, token handling, retries,
   timezones, conflicts, HA refresh, stale states and additive migrations; live
   provider writes, controls and OAuth renewal were not newly verified here.
4. Verify audible Pi playback, wake word, reconnect and full authenticated Voice
   flow; perform Spotify, Zigbee, Nanoleaf and Lounge physical acceptance.

No production deployment or AI-provider/model-routing/agent/memory change was
performed. Full platform stop and individual WSL restart remain intentionally
outside the bounded helper because of the unresolved host lifecycle behavior.
See [startup commands and lifecycle boundaries](../development-startup.md).
