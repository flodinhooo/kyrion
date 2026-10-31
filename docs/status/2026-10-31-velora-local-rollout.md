# Controlled V39 Voice compatibility rollout

Later continuation: [Voice latency measurement and activated sentence TTS](2026-10-31-voice-latency.md)
supersedes the active hash and unresolved stream-latency status below. This report
remains the original V39/Satellite rollout and recovery evidence.

Date: 2026-10-31. Primary checkout: `master`, starting at `e2ecdcc`.
This report supersedes the inactive-fix/runtime sections of the earlier
[Pi acceptance report](2026-10-31-pi-velora-acceptance.md), retaining its history.
Local rollout was explicitly authorized. No public deployment, paid provider
request, database migration, Flyway repair or persistent-data deletion occurred.
Calendar/HA and the other existing worktrees were preserved.

## Source, artifact and installed client

The compatibility worktree `.worktrees/core-v39-compat`, branch
`fix/core-v39-voice-compat`, starts at integrated **pre-V40** `c596fc3`.
Commit **`a30321c`** contains only HTTP/1.1 selection in `HttpAiGateway`, its
regression test, and additive Voice timing events with an integration assertion.
No migration was removed from a current build or edited. V1–V39 bytes match the
existing database. Master retains the V40 accounting implementation and receives
the same observational additions; its V40-bearing JAR was built/tested but never
started against the live database.

Active Core:

- Schema: **39** successful migrations, no checksum mismatch, no pending version,
  no active Calendar sync lease. Startup explicitly logged schema39/up to date,
  with no migration necessary.
- Pinned JAR: `.run/dev-recovery/v39-voice-rollout/core-runtime.jar`.
- SHA256: `E7DA352D1039FAACB01D3C9866F3825AC4D2692DD7FA4AD9AEC7C672DA126CBD`.
- Final running copy:
  `.run/dev-recovery/guarded-start-32afe436-555e-42aa-9622-b77dd4526cd2/core-runtime.jar`,
  same hash, Java PID17128 at verification time. PIDs are observations, not restart
  selectors to reuse blindly.
- Dedicated JDK21.0.13; process-only `0.0.0.0:8080` bind. Existing exact-Pi Private
  Allow plus NonPi/NonPrivate Block guards were validated and unchanged.
  Neither global `.env` bind nor DNS/IPv6/firewall policy was relaxed.
- Both protected `core-lan.json` and `settings.json` point to this rollout pin.
  The migration gate compares actual installed checksums, not just a count.

Build from that clean source using the provisioned JDK21, from repository root:

```powershell
$env:JAVA_HOME=(Resolve-Path '.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1').Path
& .worktrees/core-v39-compat/services/core/gradlew.bat `
  -p .worktrees/core-v39-compat/services/core test bootJar --offline `
  --console=plain --no-daemon --max-workers=2 `
  '-Pkotlin.compiler.execution.strategy=in-process' '-Pkotlin.incremental=false' `
  "-Dorg.gradle.java.installations.paths=$env:JAVA_HOME"
```

The installed Satellite remains distribution version **0.1.0**, with the two
reviewed modules from `e2ecdcc` applied to its existing editable installation.
The normal user service was stopped, the old files backed up, the replacements
compiled, and the service started. Config SHA256 was checked unchanged; no
credential or enrollment was replaced. Actual installed file hashes:

| Module | SHA256 |
|---|---|
| `http_transport.py` | `98aaec7a55506e3f28bfe018164ceef2a7fd24387a9468a953084d8e04c0b815` |
| `core_client.py` | `da128fc1386ef6a022d9977b9623a6990fd835c5b45b8d83c89b17f352775c0f` |

Directory: `/home/flodinho/.local/share/kyrion/voice-satellite/src/src/kyrion_voice_satellite`.
Backup: `/home/flodinho/.local/share/kyrion/voice-satellite/rollback-20261031-125913`.
Its manifest records original files and configuration hash. IPv4-first bounded
connection selection preserves the hostname, TLS verification and IPv6 fallback;
it does not retry sent HTTP requests. The actual Pi retains both address families.
The operator probe now accepts `-InstalledClient`: **all acceptance below used
that option**, not the temporary source overlay.

## Runtime, restart and authentication evidence

The idle recovery helper was reloaded by stopping only its reviewed Node PID,
without killing its process tree. Its managed AI/STT/TTS processes nevertheless
ended with their owner. This is a real helper-reload interruption, not a transparent
reload. The new helper recovered those three services through normal startup.
PostgreSQL, Core, Ollama and Web stayed available during this helper reload;
Docker and unrelated containers remained running. No WSL/Docker reset was used.
Future helper reloads need a speech-runtime outage window; ownership remains an
operational limitation. The fresh helper now uses the guarded manifest launcher.

The reviewed old Core was stopped; the installed Pi probe reported
`CORE_UNREACHABLE` without opening a session. The new pinned Core started through
`Start-CoreLan.ps1` after the read-only database/firewall gates. Actual Pi checks:
correct hostname, reachable TCP8080, health UP, unauthenticated device request401,
authenticated Voice session, valid24-kHz greeting, explicit session closure.
No diagnostic IPv4 override was active. The installed Satellite unit recovered.

After both digital turns, the new Core was stopped again. The freshly loaded
helper's ordinary `start` selected the guarded pin and started the final running
copy above. Other services were already ready and reused. Pi authentication,
greeting and closure passed again. Global usage counts/tokens/pending state were
identical before and after this restart and reconnection: four historical/current
attempts,20688 charged tokens, zero pending. This proves no replay during this
idle reconnect; it does **not** establish in-flight audio retry deduplication.
The transport deliberately performs no such retry.

Final SQL/HTTP readiness: all **seven** services passed (PostgreSQL, Web, Core,
AI, Ollama, STT, TTS). Unrelated `suprise-db-1` and `narutodnd-postgres-1` remained
running. A full Host/WSL reboot was not performed with foreign work active.

**Gateway remains unaccepted.** Its system unit is active and its journal reports
current successful heartbeats, but this local database has one Gateway row with
last_seen_at `2026-08-28 18:03:36.842583+00`, zero fresh heartbeats. No current
Gateway HTTP connection was identified in a short unprivileged socket sample;
that absence does not identify its destination. `/etc/kyrion-gateway/agent.json`
is restricted to `kyrion-gateway`; SSH user `flodinho` cannot read it and
`sudo -n` requires a password. Do not infer successful local integration from
the journal alone or expose the credential to diagnose this.

The remaining privileged step is to inspect **only** the configured Core URL as
the Gateway service user, compare it with the guarded Windows endpoint, and
correct/restart the scoped Gateway service if needed. Preserve its existing
credential and enrollment. Then demand an authenticated update to the existing
`gateway_node.last_seen_at` in this database within two heartbeat periods.
If IPv6-first blocking is confirmed there too, use a service-specific bounded
transport correction; do not globally disable IPv6 or broaden firewall guards.

## Complete digital dialogs and timing limits

Reproduction:

```powershell
& infrastructure/dev/Invoke-VeloraProbe.ps1 -Mode fixture `
  -Fixture .run/dev-recovery/pi-acceptance/synthetic-question.wav `
  -Play -InstalledClient
```

The local synthetic German input is3.64s, mono PCM16/16kHz,45 VAD-positive80ms
frames. It is digital input, not live microphone speech or a wake-word test.
STT returned “Eckley, sag mir bitte kurz, warum der Himmel blau ist.”: the opening
name was mistranscribed, but the neutral question was retained. Both responses
correctly explained Rayleigh scattering. The second answer was149 characters:
“Der Himmel ist blau, weil die Luftmoleküle das blaue Licht der Sonne stärker
streuen als das rote Licht. Dieses Phänomen nennt man Rayleigh-Streuung.”

Each turn produced a separate processing WAV and a nonempty, parseable answer
WAV. The configured Pi PipeWire playback command completed for the answer.
The Core's actual AI calls `/v1/chat/stream` returned **HTTP200**, no422 in these
turns. Catalog calls and synthesis also returned200. No request went to a cloud
provider. The separate real Gemma smoke returned `OK.`, input833/output3 tokens,
usage and completion, no error.

All values below are actual Pi monotonic measurements in milliseconds, starting
immediately before submitting the complete fixture. They include transport and
client processing, and are **not acoustic speech-end or first-audible timestamps**.

| Measurement | Dialog1 | Dialog2 |
|---|---:|---:|
| Final transcript received | 1360 | 1606 |
| First processing audio received | 25083 | 14643 |
| First model-delta marker received | 26089 | 15644 |
| First answer audio received | 26199 | 15719 |
| Answer playback process invoked | 26199 | 15719 |
| Turn returned after playback | 43325 | 24817 |

The first-delta metric is the **Pi's receipt** of `model.first_delta`; it must not
be interpreted as the model's generation timestamp. Core logs already show LLM
completion4797/3636ms after its STT-start boundary, before those receipt values.
Cached processing audio was flushed after1277/1580ms server-side, but received
much later. Stream delivery/client buffering or scheduling latency therefore
remains an open performance investigation; do not attribute the whole delay to
Gemma. Raw first-token generation time was not independently captured, nor was
actual acoustic onset. The operator result now labels its timing basis explicitly.

Read-only persisted checks, one attempt per synthetic conversation:

| Conversation | Messages | Model usage input/output | Charged tokens | Final states |
|---|---|---|---:|---|
| `8877fd81-a69c-41a4-90f1-4a52b5514b8f` | one user, one assistant |987/68|1055|usage `reported`, session `closed`|
| `85f65b3f-6e2f-4dec-8604-43d05195a494` | one user, one assistant |987/38|1025|usage `reported`, session `closed`|

Private local evidence: `.run/dev-recovery/v39-voice-rollout/dialogue-{1,2}.jsonl`,
`usage-before-restart.json`, and the guarded-start Core/AI logs. These contain
synthetic test data, are ignored, and are not committed as installation data.

## Human acceptance still required

Fresh real USB microphone check:16000Hz/mono/PCM16,47360 samples, RMS13.29,
zero speech frames, max wake score0.00099. ALSA and the ONNX detector ran; the
Satellite unit was restored. Nobody supplied a verified wake phrase. ONNX's GPU
discovery warning was nonfatal. No ambient recording was saved.

At the Pi, with the normal Satellite service active:

1. Say **“Hey Velora”**, wait for the greeting, ask a neutral German question.
   Confirm wake detection, actual speaker audibility, intelligibility and a
   sensible spoken answer. Record speech end, first audible answer and perceived
   delay using a stopwatch/video. Processing audio is not the answer.
2. End the session, repeat a second wake/dialog to check lifecycle and absence
   of replay. Compare correlated turn IDs, one usage entry and closed sessions.
3. Optionally run bounded operator observation with
   `Invoke-VeloraProbe.ps1 -Mode capture -CaptureSeconds 15 -InstalledClient`;
   this temporarily owns the microphone, so it is separate from normal-service
   wake acceptance. `-Mode manual -Play -InstalledClient` provides greeting,
   `READY_FOR_GERMAN_SPEECH`, live VAD/STT/dialog and playback observation.

An on-site person was asked about availability; no observation was supplied.
Software playback success is not evidence of human-audible output or wake recall.

## Checks, recovery and remaining gates

- V39 compatibility branch: full Core suite **289 tests**, zero failures/errors/
  skips; `bootJar` passed. Master: full Core suite **308 tests**, zero failures/
  errors/skips; `bootJar` passed, including the V40 accounting regressions and
  isolated restore rehearsal. Existing compiler deprecation/nullability warnings
  remain. No Core formatter/linter task is configured separately.
- Satellite/runtime-gate Python: **74 passed**; changed-file Ruff lint/format
  passed. Targeted probe assertions were rerun after timing-label changes.
- Relevant infrastructure Node suites: **25 passed**. PowerShell guard checks
  passed; the updated wrapper also executed on real Pi paths. Git whitespace
  checks passed. Web/AI implementation unchanged; no new Web build is claimed.

Core recovery: `.run/dev-recovery/v39-voice-rollout/previous-core-lan.json` and
`previous-settings.json` preserve the original pin/settings; the old JAR hash is
`11C48077D7BAEA19F1873435EA8EF7BE9E5C47841043300C27FA2D4CC6981B5D`.
During a quiet service window identify/review the current Core using
`Set-CoreLan.ps1`, stop only its managed Core tree, restore those two protected
JSON files, then run `Start-CoreLan.ps1` and repeat Pi/auth checks. Reload the
helper in a speech-runtime outage window if its cached settings must change.
There is no SQL rollback because no schema/data migration occurred. Returning
to that old binary also restores its known h2c Voice failure.

Satellite recovery: stop only the user Satellite unit; read the backup manifest,
restore its listed files to its recorded directory and remove only newly added
`http_transport.py` if absent from `previousFiles`; start the unit and check its
journal/config hash. Keep the rollback folder and protected config/credential.
The old client restores the known hostname/IPv6 delay, so do not call it accepted.

Open **hardware**: human wake, two heard dialogs, acoustic latency/quality.
Open **operations**: privileged Gateway target/heartbeat diagnosis, stream latency,
helper child-lifetime isolation and full host cold-start proof.
Open **accounting/V40**: durable accounting remains tested on master/test DBs,
not active in this V39 compatibility artifact; follow the separate
[V40 procedure](../v40-rollout.md) for backup/restore and explicit migration approval.
Open **cloud**: real provider/key/model/billing acceptance and spending approval.
All cloud providers remain disabled/unconfigured; no cloud cost was incurred.
