# Local Voice latency investigation and activation

Starting points: `master` at `76e0edb`, active V39 compatibility branch at
`a30321c`. Calendar/HA and other existing worktrees were preserved. This is an
authorized local rollout only: no cloud requests, public deployment, V40
migration, Flyway history change, Docker reset or host reboot.

## Final active artifacts and validation

Active compatibility branch: `fix/core-v39-voice-compat`, **`ba372d0`**, including
sentence/flush commit `3921bd8` and the tested timing-disconnect reservation fix.
Both changes are also applied on master. The final pin is
`.run/dev-recovery/voice-latency/core-runtime-final.jar`, SHA256
**`2560AE86B4C5B265C4F28231B351A887520725CAD25D6B135230A6EF9F085718`**.
The actual helper-managed running copy is
`.run/dev-recovery/guarded-start-db8af593-5b72-4397-99cd-2fd6c7510433/core-runtime.jar`
with the same hash (PID8688 at verification). Both protected JSON pin/settings
files select this final artifact; default sentence audio is enabled. Schema39,
all installed migration checksums, zero pending versions and zero active sync
leases were verified again. The master build containing V40 was never started.

AI uses the repository's tested Python source, restarted through the existing
scoped helper; Chatterbox uses the restarted WSL script and existing provisioned
weights/Velora reference. Their content hashes, unchanged since activation:

| Source | SHA256 |
|---|---|
| `services/ai/src/kyrion_ai/app.py` | `19b3dcef54f18a103f37df3d6ac2e28ba5e700e589bef1a3b6fde5fe5d160502` |
| `services/ai/src/kyrion_ai/voice_trace.py` | `76c6a0c28980fe9723fd344f6552f530e27ec1ff12eaabde9d71591c7afaac00` |
| `services/ai/src/kyrion_ai/providers/ollama.py` | `6d7a9efe30ed62c25fe42f7fa92c4c7381d8817abc01b4345575a8e88eada57a` |
| `services/ai/src/kyrion_ai/speech.py` | `c62bf87d77c8d1c5a3221f5d80812432f97e6d7962cf46bca301e3f1737c81c0` |
| `services/ai/runtime/chatterbox_tts_server.py` | `66501b3670eea9030e259a81c11c9079120fceedc7affdb5fb54ef61ecccc5a3` |

Validation: full Core tests/`bootJar` passed on both branches: **292 V39 tests**
and **311 master tests**, zero failures/errors/skips. **168 AI tests**, **75
Satellite/runtime-gate tests**, and **25 infrastructure Node tests** passed.
Changed Python Ruff lint/format and PowerShell parsing passed; the wrapper was
also exercised on the Pi. Existing Core warnings and one upstream Starlette
TestClient deprecation remain. No separate Core lint/formatter task is configured.
Web implementation was unchanged; no Web build is claimed. Final seven-service
readiness and authenticated Pi checks are separate from these automated tests.

## Measurement contract and evidence

One UUID, the Satellite turn ID, now follows Core, the AI stream and STT/TTS
requests via `X-Kyrion-Correlation-Id`. Only UUIDs, stage names, lengths, numeric
usage/performance counters and monotonic times are logged. Invalid trace headers
are ignored. No credential, model token text or private dialog body is logged.
Operator fixtures may still report their explicitly synthetic text.

Pi uses `time.monotonic`, Core uses `System.nanoTime`, AI and the WSL TTS runtime
use process-local monotonic nanoseconds. No cross-machine clock synchronization
was established; absolute timestamps from different processes are **not**
subtracted. Pi upload completion, transcript/event receipt, audio receipt and
playback-call times share the Pi's own input-submission boundary. Core stage
durations share its accepted-body boundary, after upload. AI records request/
worker/first-delta/forwarding boundaries; Ollama supplies load/prompt/evaluation
durations. TTS measures lock queue and actual generation separately.

`firstModelOutputMs` remains **Pi receipt**, not generation time. The separate
`coreEvents` entries retain `coreElapsedMs` and `piReceivedMs`. Actual first
nonempty provider delta is measured in AI and Core before final generation.
`answer.audio.ready.N` precedes publication of a complete valid sentence WAV;
`published.audio.chunk` follows servlet flushing. Pi playback is synchronous:
events received after playback resumes can be delayed by the preceding WAV.
Those delays must not be relabeled network latency. The playback metric is the
software playback-method invocation; OS/acoustic output onset is not established.

Private evidence under `.run/dev-recovery/voice-latency/` includes per-run JSONL,
`summary.json`, same-text TTS controls, prior pins/settings/source backups and
immutable JARs. Core logs live beside each guarded-start copy; AI/TTS logs are
`.run/dev-recovery/{ai,tts}.log`.

## Proven bottlenecks and bounded correction

Before changes, a raw Pi run delivered transcript at1004ms, but processing audio
and the first model marker only at32926ms. A separate `read1` trace received
partial body bytes by933ms but could not parse the complete processing event
until20644ms. Isolated chunked Python HTTP tests delivered frames immediately;
changing the Python reader was not supported as the fix. No Satellite transport
change was made in this run.

Core now writes each NDJSON event **with its newline in one write**, flushes the
stream and explicitly calls `HttpServletResponse.flushBuffer()`. With whole-
answer TTS still selected, processing audio arrived at1526ms and the first model
marker at4182ms. This establishes correction at the servlet framing/flush
boundary; it does not claim an exact internal Tomcat/wrapper defect was debugged.
IDE triage found no active JVM session and only npm run configurations, so the
evidence is instrumented runtime/HTTP behavior, not debugger frame values.

That instrumented whole-answer control proved the larger remaining bottleneck:
TTS consumed **18706ms generation, zero lock-queue ms**, with19161ms Core TTS
roundtrip and first answer audio at24867ms. Model dispatch-to-completion was
3194ms, not the former26-second Pi marker. The prompt was987 tokens. The initial
three optimized warm runs generated at approximately82–89 tokens/s; no prompt,
model, voice or generation-parameter change was needed.

Only dynamic dialogue audio is now split into complete, ordered sentences.
Small fragments are grouped; at most eight synthesis requests retain all text.
The full model answer and usage still complete before TTS begins. Existing
`audio.chunk` playback preserves order, and synthesis of the next sentence can
overlap Pi playback of the preceding one. There are no background TTS jobs,
parallel syntheses or HTTP retries. Fixed/template/action audio stays on its
existing path. Core validates session permission before each synthesis and again
before publishing audio. A local TTS already in progress may finish after a
disconnect; its audio is not published to a closed session.

Tracing callbacks after reservation are inside the existing settlement/release
boundary and before invocation is marked. Regression tests disconnect at both
post-context and pre-dispatch events: no provider call, no charge and no pending
reservation. This avoids introducing a telemetry-related accounting leak.

An independent same-text control synthesized the identical318-character answer
in33688ms versus9344ms for its76-character first sentence, with the same Velora
voice and valid WAVs. This is a synthesis control, not a Pi dialog measurement;
TTS is stochastic and the samples are not a throughput guarantee.

## Initial controlled comparison

All runs used the same3.64-second16-kHz mono German fixture,45 VAD-positive
frames, fresh authenticated conversations and installed Satellite client. The
STT name was imperfect, but the sky question was preserved. Answers correctly
explained Rayleigh scattering. Each successful run had valid answer WAVs,
completed PipeWire playback, one user/assistant pair, exactly one `reported`
Gemma usage attempt and a closed session. Input usage was987 tokens throughout;
answer lengths varied because generation was not changed or forced deterministic.

These first measurements used V39 commit `3921bd8`, JAR SHA256
`5388CA7F021CE34BC343DE8259217EF979E9688F2D4019BAA793B4DE9B4AE9E0`.
The control set process-only Spring property
`kyrion.voice.sentence-audio-enabled=false`; default-enabled runs used the same
binary via the protected helper. Core/AI/TTS services were ready for all runs.
The cold run explicitly unloaded only `gemma3:4b`; `/api/ps` confirmed it absent.
Its measured model load was3348ms versus4–5ms warm. This was a model-cold run,
not a host or speech-runtime cold boot.

All table values are milliseconds. STT/context/model/TTS columns are **within
Core**; upload/transcript/audio/end columns are **within Pi**.

| Run | Upload end | Final transcript | STT | Context/routing | Model request to first delta / completion | First TTS roundtrip | First answer / playback call | End after playback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Whole-answer control |20|1209|1094|812|1800 /3194|19161|24867|41698|
| Sentence, model cold |13|1064|944|798|4115 /4552|6969|13751|23798|
| Sentence, warm1 |19|909|876|443|807 /1482|7202|10235|26299|
| Sentence, warm2 |15|900|871|402|773 /1564|5542|8552|28041|
| Sentence, warm3 |14|895|866|511|810 /1693|6429|9699|35557|

First-sentence backend compute was6705/6945/5189/6039ms; lock queue was zero in
each case. AI first-delta latency from its dispatch was4078/766/734/781ms;
its first-delta forwarding boundary added less than the1ms measurement resolution.
Warm action interpretation took19/40/22ms and involved no device execution.
Personal/knowledge retrieval was disabled for these unknown-speaker turns;
context timing includes catalog/routing, context assembly and reservation.
At the Pi, answer-ready marker to decoded first WAV was43/46/27/30ms for the
cold/warm runs. This is a same-Pi delivery/decoding interval, not one-way latency.

Initial warm median:9699ms, versus24867ms whole-answer control (61% less time to
first answer). Response lengths143/220/264/327 characters versus318 control
must be considered when comparing stochastic end-to-end runs. Overall dialogue
completion was not consistently reduced; the goal here was earlier first speech.
**Under three seconds was not achieved.** The selected batch TTS still spends
roughly5–7 seconds computing the first sentence, and sentence boundaries can
produce pauses. Human prosody/continuity remains unaccepted.

## Repeated measurements on the final active artifact

After the reservation-disconnect fix, `ba372d0` was built, gated and activated
through a scoped helper Core restart. The full cold/three-warm series was
repeated on that final hash, with the same fixture and installed client:

| Run | Upload end | Final transcript | STT | Context/routing | Model request to first delta / completion | First TTS roundtrip | First answer / playback call | End after playback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Final model cold |15|1075|962|800|4194 /5038|5788|13019|35531|
| Final warm1 |14|1033|1003|467|870 /2079|5979|9719|32865|
| Final warm2 |14|894|843|409|848 /2085|5841|9384|46054|
| Final warm3 |15|866|836|418|856 /1470|6047|8971|25974|

Final warm median: **9384ms**,62.3% below the24867ms whole-answer control.
The primary improvement is time to first spoken-answer WAV, not total completion.
The model-cold load was3378ms; warm loads4–5ms. AI dispatch-to-first-delta was
4156/829/828/828ms. Actual TTS generation for the first sentence took
5401/5599/5453/5818ms, all with zero measured lock wait. Core TTS roundtrip also
includes HTTP, worker and WAV handling. Ollama's load/prompt/evaluation counters
do not expose an exact server queue duration; unclassified overhead is not
reported as queueing or GPU computation.

All four runs completed valid Pi playback, exactly one usage row and a closed
session. Reported input/output tokens were987/66,987/66,987/97 and987/48;
charges were1053,1053,1084 and1035 tokens. Each conversation has one user and one
assistant message. Answer lengths were281/282/430/205 characters and chunk
counts3/4/5/2. Content explained the correct phenomenon; the last response had a
minor German grammar error, so these results do not establish production answer
quality. Raw fixture-end to first audible output remains unmeasured.

Final abort `301e95cc-eabf-4a30-9339-e168a2b589d4` again played one answer chunk,
then closed/disconnected. The already completed generation settled once
(987/83 tokens,1070 charged), with no assistant message falsely marked complete.
No second answer chunk was published. A fresh installed-client session then
authenticated, received valid greeting audio and closed. No replay or additional
model invocation was observed. There are zero pending usage attempts.
The legacy V39 settlement audit does not carry the request correlation ID, so
zero directly correlated audit rows must not be mistaken for missing auditing;
per-request audit idempotency remains part of the separately gated V40 work.

## Cancellation, operation and recovery

Initial abort ID `518ec18c-9c66-4b8e-9f56-d335ec43579d` played exactly one answer
chunk, then deliberately disconnected and closed its session. Exactly one
model usage attempt remained `reported` (the model had completed), one user
message and no fabricated completed assistant response. No second answer chunk
was published. A subsequent fresh conversation completed three ordered chunks,
one usage attempt and normal closure; no old audio was replayed.

The guarded LAN launcher, exact-Pi firewall scope, credentials and schema39 are
retained. The AI process was restarted through its scoped helper action. Only
the identified Chatterbox Linux PID was stopped for the telemetry update; normal
helper startup restored it (39.8-second initialization), without stopping STT,
Docker, WSL or foreign work. The helper itself was not reloaded.

Gateway remains separate: one database row, last heartbeat
`2026-08-28 18:03:36.842583+00`, zero fresh arrivals. SSH user `flodinho` still
cannot read the service-owned config; `sudo -n -l` requires a password. A person
with privilege must inspect only its configured scheme/host/port, preserve its
credentials, fix the target if needed and prove a fresh authenticated
`gateway_node.last_seen_at` update in this Core. Journal success is not acceptance.

Rollback pins/settings are `voice-latency/previous-{core-lan,settings}.json`;
they retain the previously accepted E7DA352D… V39 artifact. Stop only the reviewed
managed Core, restore those protected JSON files, restart through the guarded
launcher and repeat Pi/auth checks. Keep the immutable prior binaries. No SQL
rollback is involved. AI prior source files are in `voice-latency/rollback-ai/`;
revert the corresponding source changes including the new trace module and
restart only AI/TTS in a quiet speech window if necessary. Preserve the selected
voice assets and Satellite config/credential. Current Satellite stays0.1.0 with
the previous installed HTTP/IPv4 fixes and hashes from the rollout report.

At the Pi, still required: say **“Hey Velora”**, ask a neutral German question,
hear and judge the actual answer, then end and repeat a second dialog. Record
human speech end and first audible answer with a stopwatch/video; distinguish
waiting audio. Judge volume, intelligibility, sentence pauses and answer quality.
No on-site observation was supplied. No acoustic/wake acceptance or safe full
host reboot is claimed. Cloud spending and live V40 rollout remain closed gates.
