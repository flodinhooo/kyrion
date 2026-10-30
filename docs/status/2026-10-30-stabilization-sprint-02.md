# Stabilization sprint 02 evidence

Date: 2026-10-30. Existing checkout; no new branch/worktree or production deployment.
Parallel AI/provider/model/context changes were preserved. Some shared source was
committed/formatted by the other process while verification was running; the
results below identify the checks actually run, not a single immutable release.

## Implemented

- Fixed a real Calendar deletion regression. Core's Unit-returning controller
  acknowledges deletion with empty HTTP 200; the Web proxy previously parsed JSON
  and returned a false 503 after the deletion completed. Successful DELETE now
  becomes empty 204; errors, revision checks, authentication and CSRF remain.
  Regression fixtures cover empty 200/204, conflict, missing session and CSRF.
- Added bounded diagnostics, per-service probe error/latency metadata and an
  observation tool that retains outages after recovery. Raw environment values,
  credentials, request bodies, provider payloads and kernel log text are not
  persisted. Docker inspection requests state metadata rather than configuration.
- Added explicit PostgreSQL restart using a 120-second graceful stop, existing
  container/data, SQL readiness and bounded Core reconnect. The first test exposed
  a transient false failure immediately after SQL recovery; the fixed second
  invocation exited successfully with all seven services ready.
- Repeated starts now join an active job or retry the helper's short cooldown
  within a five-attempt bound. Authorization/permanent failures are not retried;
  a restart never silently joins someone else's running job. Two successive real
  CLI starts completed and preserved all running local services.
- Added fixed-list scoped Windows restart support in helper v5. It preserves
  external processes, WSL and untargeted/Pi services. Failed process spawns are
  removed from the managed map instead of being mistaken for loading runtimes.
  The existing live helper was not interrupted merely to activate this source.
- Added repeatable public/authenticated demo smoke checks, marked local-calendar
  CRUD/cleanup, HA manual/periodic refresh observation, and a demo checklist.
  Custom `.next-*` build output is excluded from Git/ESLint automatically.

## WSL/Docker findings

The retained Docker host log gives a concrete shared-host sequence on October 30:

- **17:43:26 UTC**: WSL bootstrap/proxy processes exit with status 1; Docker reports
  `Wsl/Service/0x80072746` and transitions its Linux/WSL engine to stopping.
- **17:43:59 UTC**: bootstrap failures continue during recovery.
- **17:44:50 UTC**: Docker reports its WSL engine running again. The WSL boot ID
  changed from the previous recorded boot; unrelated Docker projects also restarted.
- **17:46:29 UTC**: PostgreSQL's container starts again. It reports an unclean
  previous run and completes WAL recovery at **17:47:57 UTC**.

The most strongly supported failure domain is the shared WSL VM/interop layer,
not an isolated PostgreSQL or Chatterbox container failure. The initiating cause
is unresolved. Available current/previous kernel logs contain no OOM or panic
markers; PostgreSQL reports `OOMKilled=false`. Recovery logs contain init timeouts,
two interop signal-5 events and DXG query warnings. Those events follow/recur around
recovery and do not by themselves establish a CUDA driver failure.

Measured configuration: WSL 2.3.24, kernel 5.15.153.1, Windows build 26300.9818,
RTX 2070 / 8 GiB, NVIDIA 610.88; approximately 27 GiB available in WSL with 8 GiB
unused swap and approximately 25-27 GiB free on the 64-GiB Windows host. No custom
`.wslconfig` was present. Windows System/Application/Hyper-V log queries provided
no matching causal crash, sleep or OOM record. This is absence of retained
evidence, not proof that pressure or external termination never occurred.

TTS model activity overlaps the interruption, but simultaneous operator activity
and missing pre-failure telemetry prevent causal attribution. No global WSL/Docker
termination, automatic restart loop, blind resource-limit increase or host reboot
was performed. Docker recommends current WSL releases; a coordinated compatibility
update/reboot is follow-up, not a proven fix.
See [Docker WSL best practices](https://docs.docker.com/desktop/features/wsl/best-practices/).

## Real runtime and integration checks

- Two controlled PostgreSQL stop/start cycles retained the existing container,
  flushed clean shutdown checkpoints and started without crash-recovery messages.
  Other Docker projects and the WSL boot were preserved. Core recovered its
  database connections; the second CLI invocation passed end to end.
- A five-minute observation recorded 30 samples with one failed Core probe at
  approximately 221 seconds. WSL boot ID and PostgreSQL start time were unchanged.
  It correctly exited nonzero; this was not an all-green uptime test. Subsequent
  probes were extended with cause/latency metadata for further investigation.
- A subsequent two-minute observation passed all 13 samples with zero failures,
  unchanged WSL boot/database start and complete diagnostics. It does not erase
  the failed five-minute result or prove overnight reliability.
- An isolated helper-v5 HTTP check returned 401 without the operator key and 400
  for a forbidden WSL restart target, retaining idle state. Only that empty test
  helper was stopped afterward; no managed runtime was launched or interrupted.
- Signed-in browser checks passed Dashboard, Home, Devices, Calendar, Plugins,
  Lounge, Chat, System services, Users and Roles without JS/server errors.
  Inventory contained 13 devices, four rooms and one gateway. API reachability
  does not establish physical state correctness or actuator success.
- Local Calendar: create, update, timezone/instant persistence, stale-revision 409
  and cleanup passed against the live stack after the DELETE fix. Only new marked
  local test events were created/deleted. Local operation remained usable with
  Google authorization invalid.
- HA was configured/healthy, manually imported five devices and advanced its
  success timestamp through the existing background scheduler. Observation uses
  status reads only after import, avoiding accidental on-demand-refresh evidence.
  No HA outage, token replacement or physical device command was forced.
- Google Calendar discovery returned 409 `GOOGLE_REAUTHORIZATION_REQUIRED`; the
  stored connection also reports `reauthorizationRequired=true`. Live pagination,
  provider writes/sync and renewed OAuth remain blocked. The smoke exits nonzero
  rather than hiding these failures. Normal interactive reauthorization was
  requested; no cached bearer token was extracted or used.
- Spotify status/device enumeration succeeded (three to four devices over time).
  Receiver, Voice Satellite, Media Player and Gateway report active over pinned
  SSH. Media Player rejected malformed JSON without launching playback.
- Pi DNS resolves the Windows Core hostname, but LAN TCP/HTTP to Core timed out.
  Core's source default is loopback, no explicit shared bind override was present,
  and firewall scope allows the reserved Pi IPs. No firewall/Pi configuration was
  weakened/changed. Full authenticated Voice, Zigbee and gateway execution toward
  the Windows Core remain unverified until the LAN path is restored.
- Real existing-voice TTS -> WAV -> Parakeet transcription passed: both HTTP 200,
  mono 24 kHz, 1.52-second audio, expected German word recognized, 4.62 seconds
  total. This is generated-audio API evidence, not microphone/wake-word or audible
  speaker acceptance. No disruptive physical action or playback was initiated.

## Automated verification

| Check                                              | Result                                                         |
|----------------------------------------------------|----------------------------------------------------------------|
| Core tests / bootJar                               | 222 passed, zero failures/errors/skips; isolated JDK 21/output |
| Web tests                                          | 145 passed / 48 files, including DELETE regressions            |
| Web ESLint / TypeScript                            | Passed on the final checked source                             |
| Next production build                              | Passed using `.next-sprint02-build`                            |
| AI tests                                           | 163 passed on final rerun; one upstream deprecation warning    |
| Voice Satellite                                    | 50 passed                                                      |
| Gateway                                            | 17 passed, 1 Linux-specific metrics test skipped on Windows    |
| Node diagnostics/demo/readiness/policy/observation | 28 passed                                                      |
| Compose config / Node syntax / whitespace          | Passed                                                         |

An initial AI run had one failure in the parallel multi-provider 30-ms cancellation
test (158 passed); its isolated rerun and subsequent complete suite passed. An
initial Web build/typecheck failed in the parallel chat sensitivity type; after
that file was corrected by the other process, the final production build and
typecheck passed. Those AI/chat files were not edited by this stabilization work.
No Kotlin formatter/linter task is configured; TTS Ruff checks passed.

## Demo gates still open

1. Reauthorize Google through its normal UI and repeat provider-specific checks.
2. Coordinate the Windows Core LAN bind/start with the parallel process, then
   verify Pi authentication and microphone-to-speaker Voice.
3. Investigate the isolated Core probe failure with the new metadata and run an
   extended observation; five minutes cannot establish long-term reliability.
4. Obtain approval for a coordinated Windows cold-start test/possible WSL update.
5. Freeze the parallel AI/demo build and verify actual chat plus authorized
   Spotify, Zigbee and Nanoleaf physical actions. Page rendering alone is not
   completion of these flows.

Commands and the ordered demonstration are in the [demo checklist](../demo-readiness-2026-10-31.md).
