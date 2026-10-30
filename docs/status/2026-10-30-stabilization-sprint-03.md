# Sprint 03: Google acceptance and Pi-Core remediation

Date: 2026-10-30. Work remains in the existing checkout. Parallel K-AI/Velora
source changes were preserved; no production deployment or database reset occurred.

## Google: working after the user's reauthorization

The user clarified that Google was reauthorized after the earlier revoked-token
observations. A real October 31 event created through Kyrion appeared on Samsung.
That is user-confirmed delivery, not an observation made by the automated tests.

The current authenticated smoke independently confirmed configured/connected,
`reauthorizationRequired=false`, three calendars and successful provider access.
No authorization flow or token invalidation was initiated.

The new opt-in `--google-calendar` smoke passed all seven live checks: existing
authorization, marked event creation, stable Google ID/offset-range readback,
conditional edit, stale-ETag 409, edited provider data visible in Kyrion's combined
view, and 204 deletion with confirmed absence. Only its generated, uniquely
marked test event was modified/deleted. It never invokes actor-wide sync or
touches existing personal appointments. Cleanup checks exact generated ID,
marker, description, ETag and nonrecurring scope before deletion.

This proves Google write/readback and presentation through the existing Core
boundary. A Samsung-origin edit of a linked local event was not performed by the
agent; use the explicit manual procedure. More than 100 live events were not
seeded; provider pagination and token refresh remain covered by existing fixtures.

One software defect was fixed: the direct Web Google event GET discarded
`calendarId`, `start` and `end`, silently using primary/default range. It now
forwards only those three filters, preserves timezone offsets and avoids cached
reads. Four route regressions cover filtering, omitted filters, real provider
authorization errors without automatic OAuth, and unauthenticated access denial.

## Pi-Core: exact cause and approval boundary

Pi DNS resolves `kyrion-core.home` to the current Windows private Ethernet address.
Core is a native JVM on port 8080, not a published Docker container; its listener
is loopback and there is no `KYRION_CORE_ADDRESS` override in the local shared
configuration. The Pi's TCP/HTTP attempts time out. The existing firewall is
enabled and permits Private/TCP 8080 only from the two reserved Pi addresses.
Windows-to-Pi pinned SSH and audio file transfer work.

`Set-CoreLan.ps1` prepares/validates the smallest correction: explicit local LAN
bind, preserved current runtime JAR and a targeted Core restart. The dry-run
passed and reports `apply=false`. All installed Flyway checksums matched that
running JAR and no Calendar synchronization lease was active at the initial
precheck. Runtime/file identity must be checked again before application.

Automatic approval review rejected actual application because it broadens the
network security boundary and force-restarts Core. Explicit approval was requested
and is pending. The rejected command did not run; `.env`, listener, firewall,
database and Pi configuration remain unchanged. This is a prepared repair, not a
claim that the Pi can already reach Windows Core.

## Voice and stability evidence

- Pi Gateway, Voice Satellite, Spotify Receiver and Media Player report active.
  The satellite points to the correct Core hostname and has its enrolled
  configuration/model files. Credentials were not exported or printed.
- The installed Pi wake model loaded and rejected eight silence frames. This
  checks model/inference readiness without microphone capture or speaker output.
- Existing-voice TTS generated valid mono 24-kHz WAV. An actual Windows-to-Pi
  SSH transfer preserved its SHA-256 and WAV format; only the uniquely named
  temporary Pi file was removed afterward. No audio was played.
- A normal-client session/greeting probe is prepared for after the LAN change;
  unit regressions verify no credential use before network readiness, session
  cleanup on greeting failure and valid WAV handling without capture/playback.
  Authenticated Pi-to-Core session/greeting and the acoustic path remain untested.
- WSL boot ID and database start time remain unchanged. A two-minute observation
  had 13 samples and one Core `PROBE_TIMEOUT` at 2007 ms; it exited nonzero.
  This is an isolated Core probe failure, not evidence of another global WSL reset.
- Diagnostics now collect bounded Windows sleep/resume, crash, storage, resource
  exhaustion and GPU-reset event metadata alongside WSL/Docker state. No raw
  messages, command lines, credentials or provider payloads are persisted. The
  current two-hour query returned no matching causal events. The initiating
  cause of the historical `0x80072746` interruption remains unresolved; no resource
  limits, driver/runtime versions or global lifecycle were changed.

## Verification and current limits

New/targeted checks: 30 Node tests passed; 53 Voice Satellite tests passed;
18 TTS/speech tests and Ruff checks passed; Gateway 17 passed with one expected
Linux-only skip on Windows. The LAN plan was executed read-only; Pi diagnostics
correctly report an unreachable Core. The authenticated Google browser run passed.

The broad Web suite initially had three failing tests in the concurrently edited
chat route; a later run passed all 149 tests. An early production build/typecheck
failed in the new parallel AI settings component (`taskNames`), and lint identified
its effect-state handling. Those files were not edited by stabilization.

The first full Core run built its JAR but the integration fixture's disposable
PostgreSQL container timed out waiting for startup logs (189 tests passed, one
initialization failure). The running database remained healthy. A retry and final
Web build checks then completed successfully; no timeout/fixture changes were
made merely to hide this failure.

Final executed results (the shared source continued to evolve concurrently):

| Check                                      | Result                                                                      |
|--------------------------------------------|-----------------------------------------------------------------------------|
| Core full suite / bootJar                  | 233 tests passed, zero failures/errors/skips; build passed                  |
| Web full suite                             | 149 tests passed across 49 files, including four new Google GET regressions |
| Web ESLint / TypeScript / production build | All passed on the final checked source                                      |
| AI full suite                              | 164 passed; one upstream TestClient deprecation warning                     |
| TTS/speech targeted subset                 | 18 passed; Ruff passed                                                      |
| Voice Satellite                            | 53 passed, including three new operator-session probe regressions           |
| Gateway                                    | 17 passed, one Linux-specific metrics check skipped on Windows              |
| Node readiness/diagnostics/demo tests      | 30 passed                                                                   |
| PowerShell LAN plan                        | Syntax and real dry-run passed; application not executed                    |
| Compose config / Node syntax / whitespace  | Passed                                                                      |

The initial parallel AI UI lint/build errors were subsequently resolved by the
other process. This work did not alter its provider, routing, memory, policy or
Velora source. The new Core build was not selected for runtime deployment; the
reviewed LAN plan preserves the existing working JAR instead.

See [the reviewed LAN procedure and manual Voice/Google steps](../pi-core-and-voice-acceptance.md).
