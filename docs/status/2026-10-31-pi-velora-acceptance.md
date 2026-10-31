# Pi/Core network repair and bounded Velora acceptance

Latest: [authorized V39 rollout and successful digital dialogs](2026-10-31-velora-local-rollout.md)
supersedes the inactive Core/Satellite fixes and helper-runtime state below.
This earlier report remains evidence for the initial network diagnosis.

Date: 2026-10-31. Starting branch/revision: `master` / `4e31188`.
The existing dirty Calendar/HA worktree and other worktrees were preserved.
The active database remains V39; no candidate application, V40 migration or
Satellite package was deployed. Only the already running V39 Core artifact was
restarted with guarded LAN binding. No cloud calls were made.

## Actual network path and corrections

The Pi's configured `http://kyrion-core.home:8080` resolves to the current Windows
Ethernet address192.168.1.107. Its route uses eth0/source192.168.1.116; Wi-Fi
retains the reserved192.168.1.115 address. No stale IPv4 record was found.
Core is a native Windows Java21 process; Docker publishes PostgreSQL5432 only
for Kyrion. Existing unrelated Docker databases were left alone. Portproxy has
no relevant forwarding. WSL has a separate172.21.144.0 virtual subnet/default
gateway172.21.144.1. No Docker publishing, WSL networking, DNS or router change
was needed.

Two independent faults were observed:

1. The previous cold/manual startup used the safe loopback default. The earlier
   authorized LAN bind was process-only, so a later generic startup lost it.
   `Activate-CoreLan.ps1` validated the same running JAR, all39 installed SQL
   checksums, no pending migration/active sync lease and both existing firewall
   guards, then restarted **only Core** on0.0.0.0 with the dedicated Java21.
   Pi TCP/health/unauthenticated401 checks then passed.
2. The hostname also resolves to three IPv6 addresses. Bounded Pi probes each
   timed out at601ms for IPv6, while IPv4 connected in1ms. Existing guards
   intentionally deny non-Pi/IPv6 traffic. The installed urllib client can wait
   90/180 seconds per address before reaching IPv4. The unmodified session probe
   exceeded its25-second external bound; the existing IPv4 diagnostic passed.

The source Satellite transport now prefers IPv4 while preserving DNS hostname,
HTTP Host and TLS verification, retaining IPv6-only fallback before request bytes
are sent. TCP connection attempts share a5-second budget, at most2 seconds each;
existing read deadlines remain90/180 seconds. It never retries an HTTP request
after bytes may have been sent. OS DNS resolution remains a separate system
resolver operation; the operator wrapper imposes an outer120-second bound.

The installed Satellite package was **not replaced**. Real authenticated tests
using the corrected transport loaded its two source modules in a temporary
operator-process directory, automatically removed afterward. The default
Satellite service still needs a separately controlled client update before its
normal hostname path can be called accepted.

Network boundary checks after activation/restart:

| Origin / target | Observed result |
|---|---|
| Windows loopback IPv4 / IPv6 | Connected |
| Windows own LAN address | Connected,15ms |
| Pi hostname IPv4 | Connected,1ms |
| Pi hostname IPv6 (three addresses) | Each timed out,601ms |
| WSL → Windows virtual/LAN addresses | Each timed out,601ms; NonPi restriction retained |
| Pi health / unauthenticated device request | Health UP /401 denial |
| Pi enrolled Voice session | Opened, valid24-kHz greeting WAV, closed; no global IPv4 override with corrected probe transport |

No firewall was disabled or broadened. The two existing persistent Block guards
still restrict the dedicated executable to loopback and the two reserved Pi
IPv4 sources, with non-Private traffic blocked. The existing narrow Private Allow
remains unchanged. Gateway systemd is active, but the read-only database check
found **zero authenticated Gateway heartbeats in the last two minutes**; fresh
Gateway integration is therefore not claimed by a green systemd status.

## Restart persistence and safety

`Activate-CoreLan.ps1 -Apply -Persist` records an operator-only pin at
`.run/dev-recovery/core-lan.json`. `Start-CoreLan.ps1` refuses altered/out-of-root
artifacts, occupied ports, missing/changed firewall guards and any migration/
checksum/lease mismatch before starting. It copies the pinned JAR, uses only the
guarded Java executable and verifies local plus Pi health. It never selects the
newest build or changes the shared `.env` bind.

The recovery helper source supports an explicit `coreLanManifest` setting and
uses the guarded launcher with `-Wait`, preserving managed restart behavior.
Loopback starts also gain the read-only migration gate. Local recovery settings
were backed up and pinned to the accepted V39 artifact/manifest. An existing
helper retains its old in-memory configuration until a separately safe reload;
use the dedicated guarded launcher meanwhile. That helper reload was not tested
because prior helper termination coincided with WSL/Docker loss.

Actual controlled test: stop only the reviewed Core process, observe the Pi
probe report `CORE_UNREACHABLE` without opening a session, then run
`Start-CoreLan.ps1`. The same artifact SHA256
`11C48077D7BAEA19F1873435EA8EF7BE9E5C47841043300C27FA2D4CC6981B5D`
returned on the guarded LAN listener. Pi health/auth denial and subsequent Voice
session checks passed. All seven local services remained ready. Core's log says
39 migrations validated and no migration applied.

A full Windows/WSL reboot is **open**: two unrelated Docker projects and existing
WSL speech runtimes were running, with a documented reset hazard. They were not
interrupted to obtain reboot evidence. No persistent data, original keys,
Pi-hole/DNS configuration, provider credentials or enrollment was removed.

## Actual hardware and dialogue evidence

The Pi has its Delock USB microphone and configured Pebble V3 Bluetooth/PipeWire
sink. Capture temporarily stopped only the Satellite user unit, released ALSA,
then restored the previously active unit in `finally`. No ambient recording was
retained or submitted to Core.

- Real microphone: mono PCM16 at16000Hz,47360 samples (2.96 seconds), RMS158.59.
  WebRTC VAD marked5 frames; the ONNX detector's maximum score was0.00092.
  Nobody supplied a verified wake phrase, so this proves capture/model execution,
  **not** wake recall, STT quality or a false-negative wake result.
- A local TTS-generated German fixture, “Erkläre mir bitte kurz, warum der Himmel
  blau ist.”, was resampled to16-kHz mono PCM16, duration3.64 seconds. It was fed
  digitally through the real Pi client → authenticated Core → STT path. This
  fixture is not human microphone speech and is not a wake-word test.
- Measured on the Pi's monotonic clock for that fixture: request/capture boundary
  → transcript985ms; → first audio received1463ms; → PipeWire playback invocation
  1463ms; failure returned2292ms. PipeWire completed playback successfully.
  The audio was the **processing response**, not a completed LLM answer.
- Actual human speech-end → transcript: **not measured** (fixture input and VAD
  capture boundaries are not acoustic speech end). First model output:
  **not measured / blocked**. First audible audio and subjective quality:
  **not measured**; a successful `pw-play` exit does not establish audibility.

The ordinary local-model Voice turn failed after `llm_request`, with
`VoiceSpeechUnavailableException`. Runtime logs showed AI HTTP422 and h2c
warnings. An isolated Java21 A/B request with identical synthetic JSON proved:
HTTP/2 cleartext upgrade →422, validation error `body: Field required`;
HTTP/1.1 →200 with real Gemma text/usage/completion events. The current
`HttpAiGateway` source now explicitly selects HTTP/1.1, with a regression checking
both model-catalog and generation requests retain their bodies and omit h2c.
That fix is **not in the pinned active V39 binary**. Deploying the new V40-bearing
candidate merely to complete this test would violate this run's boundary.

Debugger triage followed the ij-debugger skill: no active JVM session and only
npm run configurations were available in IDEA; the pinned JVM had no configured
debug attachment. No debug session, suspension or logpoints were installed. The
fallback evidence is the correlated runtime stage/HTTP logs and isolated JDK
protocol A/B test, not claimed debugger values. No raw personal prompt or secret
was logged by the new operator tools.

## Remaining manual acceptance, precisely prepared

After a separately authorized compatible Core/Satellite update (or a reviewed
V39-compatible transport patch), a person at the Pi should:

```powershell
# Say "Hey Velora" during the15-second real microphone/wake observation.
& infrastructure/dev/Invoke-VeloraProbe.ps1 -Mode capture -CaptureSeconds 15
# Hear the greeting, then say the neutral German sky question after READY_FOR_GERMAN_SPEECH.
& infrastructure/dev/Invoke-VeloraProbe.ps1 -Mode manual -Play
```

Confirm the intended speaker is actually audible and intelligible. Capture a
physical stopwatch/video timestamp for speech end and first audible response,
then compare with transcript/audio-receipt and Core STT/LLM/TTS stage events.
The source Core only exposes LLM completion in Voice, not first-token timing;
do not relabel that as first model output. Repeat the existing20 DE/EN acceptance
matrix and exercise normal wake after a controlled Core outage/reconnection.
Neither a human wake/dialogue nor acoustic quality was accepted here. A person
was asked asynchronously about availability; no on-site observation was supplied.

## Validation and open gates

- Full Core tests/`bootJar`: **308 tests, zero failures/errors/skips**, including
  all accounting invariants and the real isolated dump/restore V40 rehearsal.
- Satellite tests plus runtime-gate tests: **73 passed** (65 Satellite,8 gate).
  Includes IPv4 preference, IPv6-only support, bounded connect failure, preserved
  Host/auth, TLS verification, no HTTP retry, operator action denial and absence
  of false audibility claims. Ruff and changed-file formatting passed.
- Infrastructure Node: **32 passed**; PowerShell scripts parse, manifest errors
  and missing backup manifests fail closed. JavaScript syntax/whitespace checked.
- AI/Web application code was not changed. Existing AI/Web results are not
  claimed as rerun results. The real Java HTTP/1.1 control generated local Gemma
  text; no cloud provider was configured or called.

**Hardware:** human wake, complete German dialog/acoustic latency/quality and
normal installed-client reconnection remain open behind the runtime compatibility
fix and on-site observation. **Cloud:** no spending/key/model acceptance.
**Accounting:**4e31188 invariants are unchanged/tested; provider billing lookup
and live V40 rollout remain open. **Operations:** safe helper activation/full-host
reboot, fresh Gateway heartbeat and deployment of the prepared compatibility
fixes remain separate gates. See [V40 rollout preparation](../v40-rollout.md).
