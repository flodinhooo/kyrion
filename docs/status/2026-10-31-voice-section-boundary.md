# Voice section boundaries, engine limits and playback safety

Continuation from `master` `89d41c2` and active V39 `ba372d0`. All operations were
local and authorized. Schema39, existing SQL checksums, protected LAN/firewall
rules and credentials were preserved. No V40 migration, cloud call, Docker reset,
data deletion or host reboot occurred. Calendar/HA work was untouched.

## Active corrections and provenance

- Core compatibility commit **`2488c1b`**, branch `fix/core-v39-voice-compat`.
  The same Core changes and tests are present on master. Complete Markdown bullet
  and numbered list items are now section boundaries; previously a three-item
  list could become one252-character TTS request. Introductory text stays with
  the first actual item. Minimum32 characters, maximum8 requests and retention
  of the final item remain. This never releases a standalone greeting/preamble
  as the first answer. Plain paragraph segmentation remains unchanged.
- Section events include index, character count and the shared turn UUID.
  `answer.text.released.N` records actual release to TTS. No dialog text is added
  to logs. Core still authorizes before synthesis and again before publication.
- AI reuses an owned HTTP pool for batch TTS: at most2 connections/1 keepalive.
  Pools close on application shutdown; injected clients stay caller-owned.
  There are no added synthesis jobs or generation retries. Controlled fresh
  HTTP-client construction took245–329ms, median253ms; observed pooled lookup
  was below the Windows monotonic clock's15.625ms nominal resolution, not proven
  zero. This removes repeated setup, not seconds of engine computation.
- Installed Satellite now normalizes incomplete HTTP bodies and connection resets
  during a later section to `CoreVoiceError`, closes the stream and does not retry
  or replay old audio into the next turn. Its version stays0.1.0. Configuration
  hash was checked unchanged; credential/enrollment files were not modified.

Active Core pin: `.run/dev-recovery/voice-boundary/core-runtime.jar`, SHA256
**`50A8174C1931EB7D4614AF8FF580B769831C992FC8CB6526FA3DFF54291DAE23`**.
Final normal helper-managed copy:
`.run/dev-recovery/guarded-start-2d2190b3-55b2-4c5f-ad65-305eff6a4ad5/core-runtime.jar`,
same hash, observed PID11180. Both protected pin/settings JSON files select this
artifact. Final migration/lease and LAN-guard verification passed.

AI/Satellite source hashes (the running Python processes were explicitly updated):

| Source | SHA256 |
|---|---|
| AI `app.py` | `c7b463aee45d46550202fc3bc4ad2a90e60524d6fa63d09c295b796bf0200d77` |
| AI `speech.py` | `60a8412cd840e542a6ee7c55cff5cee19a8bf72b22611dc2cbe3069fa46a2cdb` |
| Chatterbox runtime | `fc80f752e652bad5c43be979f2b689f7d4c5f2124a905e2096abea8bcd7f24f7` |
| Installed Satellite `core_client.py` | `3d8c527ffac0febcf4bd45321e1362d3f56f2913251700ee41ecdc5695febadd` |

## What still takes time

The selected Chatterbox multilingual package is **0.1.7**. Its installed
`mtl_tts.py` SHA256 is
`117c5ba0ed55812440ff7ed9e0db28b674779ca93b17533c0b6b927a80111cf8`.
Its `generate` is not a generator and the selected class has no streaming entry
point. It completes T3 speech-token inference, calls S3 audio decoding with the
complete token sequence, copies/watermarks CPU audio and only then returns a
waveform. Replacing the API response with `StreamingResponse` would not produce
earlier engine samples. A different inference implementation needs separate
quality/performance work; none was introduced here.

Instrumentation wraps those existing phase calls under the existing generation
lock, restoring methods even on exceptions. These are monotonic wall durations,
not isolated CUDA-kernel timings. Every measured section reused conditioning
(`prepare_conditionals` calls0); the model remains loaded between sections.
Parameters were unchanged: Gemma3:4b/Q4_K_M, context4096, output cap1024,
`think=false`, voice keepalive24h; model temperature1/top_k64/top_p0.95 and no fixed
seed. TTS remains Velora/de, temperature0.65/cfg_weight0.5/repetition_penalty2.
The selected reference WAV SHA256 still equals
`D2AFDC5FAA3FB6CC41756DAAAAC3DB63C30679E3BCD3E87F6DAB0055D08DAD09`.

For the problematic original list: **11603ms T3**, **2248ms decoder**, **14139ms
total generation**, **2ms WAV packaging**, zero measured generation-lock wait.
The first request after the fix still took10647ms for160 characters. This is an
engine/section-length limit, not a large WAV-serialization buffer. An independent
same-text control measured252 characters/full list at12766ms versus its126-character
intro-plus-first-item at8328ms. Both used the same voice and valid complete WAVs;
this control is TTS-only, not a Pi/acoustic latency measurement.

TTS still starts **after model completion**, not during generation. First token
to released first section took524–1159ms in the warm comparison. Even perfect
overlap cannot save more than that whole remainder; an actual first complete
sentence arrives later than the first token. No speculative parallel TTS jobs
were added to compete with the dominant first-section engine work or publish
speech before existing completion/policy/accounting gates.

## Three-question comparison

The same WAV bytes were used before/after for: (Q1) why the sky is blue, requesting
two short sentences; (Q2) lake versus river, requesting two short sentences;
(Q3) three ways to save water, requesting three short sentences. Input durations
were4.20/5.20/5.96s. WAV hashes, exact synthetic input, actual STT transcripts and
model configuration are retained in `.run/dev-recovery/voice-boundary/`.
Fixture instruction text contained an umlaut-encoding typo, and STT normalized
some wording imperfectly; inputs and each question's transcript stayed identical
before/after. This is a digital comparison, not human-speech quality acceptance.

Pi times use its monotonic clock from digital submission. Core intervals use its
own nanoTime from accepted upload. AI and Linux TTS use their own monotonic
clocks. Absolute clocks across processes/machines were not compared. Windows
Python uses GetTickCount64 (nominal15.625ms); sub-tick values are not precise.
The playback method call is not acoustic onset; actual player creation/end is
recorded separately. No waiting audio is counted as answer audio. Original model
preambles are preserved with useful content; their internal acoustic word onset
is not measured.

All values below are milliseconds. Transcript/answer columns are Pi elapsed;
context, model and release/TTS columns are Core-local intervals.

| Run | Final transcript | Context | Request→first delta | Delta→text release | TTS→first playable WAV | First answer/playback call | Answer chars |
|---|---:|---:|---:|---:|---:|---:|---:|
| Before Q1 |960|432|564|603|8707|11449|182|
| After Q1 |1111|820|1255|524|6758|10783|177|
| Before Q2 |1219|426|7612|997|11518|22017|330|
| After Q2 |1079|432|947|662|7189|10508|213|
| Before Q3 |1161|451|885|1159|14536|18396|252|
| After Q3 |1218|430|1007|980|10703|14690|293|

Across these three different questions, median first audio was18396→10783ms;
range11449–22017→10508–14690ms. **These are three samples, not a causal general
speedup estimate**: response lengths differ, the first after-run followed a Core
restart, and before-Q2 had7306ms Ollama prompt evaluation despite a resident
model (load4ms). The Q2 improvement must not be credited entirely to pooling or
segmentation. Q3 now starts a complete first list item earlier even though its
full answer grew252→293 characters. The same-text control above isolates that
structural benefit. The prior9384ms sky-question median is a different fixture
and is not a new baseline for these three inputs.

Separate model-cold Q1: first audio15170ms, explicit `/api/ps` absence before
generation and measured model load3613ms. Speech runtime was already ready;
this was not a host or TTS cold boot. **Under three seconds is not achieved.**

Every TTS section in the primary comparison is documented below. Tokens/decoder/
compute are within the TTS process; audio duration is container/sample-derived.

| Run.section | Characters | Audio ms | T3 ms | Decoder ms | Total compute ms | WAV packaging ms |
|---|---:|---:|---:|---:|---:|---:|
| Before Q1.0 |109|6280|6630|1634|8425|2|
| Before Q1.1 |72|4120|3868|1376|5264|1|
| Before Q2.0 |174|10800|9076|1821|11110|1|
| Before Q2.1 |155|8920|7387|1662|9073|1|
| Before Q3.0 |252|13440|11603|2248|14139|2|
| After Q1.0 |89|5080|5081|1221|6686|1|
| After Q1.1 |87|4880|4105|1255|5379|1|
| After Q2.0 |105|6760|5470|1439|7206|1|
| After Q2.1 |107|5880|5234|1228|6478|1|
| After Q3.0 |160|9080|8742|1579|10647|1|
| After Q3.1 |77|4800|4284|1335|5644|0|
| After Q3.2 |54|3120|3061|1019|4094|1|
| Cold Q1.0 |109|6520|6337|1473|8199|1|
| Cold Q1.1 |91|5520|4947|1319|6290|1|
| TTS abort.0 (discarded) |89|5200|4501|1255|6343|1|
| Playback abort.0 (interrupted) |92|5680|5200|1277|6918|1|
| Playback abort.1 (discarded) |106|6440|6814|1245|8085|1|
| Later-failure.0 |193|11080|11216|2593|14306|2|
| Recovery Q1.0 |90|4880|7191|1770|9261|1|
| Recovery Q1.1 |97|5800|5842|1768|7630|1|

The failed second request was rejected before the engine and has no waveform;
its planned text length was not captured by the fault proxy. These missing
measurements are not recorded as zero. Correlated logs and private
`additional-sections.json` retain the section evidence. A0ms packaging value
means below the rounded1ms resolution, not zero work.

## Playback, cancellation and later failures

After-runs played2/2/3 sections exactly once in index order. Recorded player
intervals never overlapped. Normal process duration exceeded sample duration by
36–76ms, consistent with complete software playback. The probe now rejects WAVs
whose declared PCM sample tail is missing, with a truncation regression test.
These checks do **not** prove audible word endings or uninterrupted Bluetooth
output. After-comparison inter-player gaps were341ms,8ms and5/4ms.

- **Abort during TTS:** at2835ms, no answer WAV played; session closed. The
  in-flight batch computation can finish, but Core revalidates before output and
  does not publish that section or synthesize further sections for the closed
  session. No engine-level cancellation interface exists on this path.
- **Abort during playback:** the first5.68s answer WAV's player was terminated
  after303ms. The probe failed deliberately and closed its session. No second
  answer played and no `pw-play` process remained afterward. This is a controlled
  operator interruption, not evidence of spoken barge-in.
- **Later-section fault:** a disposable loopback-only proxy returned503 exactly
  on dynamic TTS request2 (UUID `842943bf-9fc5-4e61-9e74-eb2217a5949a`). The first
  complete section played once; no second section or false completed response
  was accepted. Client reported `CoreVoiceError` and closed. Proxy and process-
  scoped Core URL override were removed in `finally`; normal guarded Core was
  restored. Initial proxy setup attempts failed before model invocation and are
  explicitly excluded from this successful fault test.
- **Recovery:** a fresh normal-path Q1 dialogue then completed two sections,
  one usage entry and closure, without old audio. It exposed a **2793ms** gap:
  next-section computation outlasted the preceding playback. Additional parallel
  TTS jobs would compete on the same locked engine; gapless sentence transitions
  are **not** accepted. Earlier first output and gapless output remain different
  goals with this batch engine.

All main/cold/recovered conversations have one user/assistant pair, exactly one
`reported` LLM attempt and closed Voice sessions. The two deliberate aborts and
later fault have one user, no fabricated completed assistant message and one
reported attempt each: generation had already completed before speech failed.
Actual provider token counts were retained; no unknown value was changed to zero.
There are zero pending attempts. V39 settlement audit correlation limitations
and the separately gated V40 accounting work are unchanged.

## Validation, operation and rollback

Full Core tests/`bootJar`: **314 master**, **295 V39**, zero failures/errors/skips.
AI **172 tests**; Satellite plus runtime gate **78 tests**; infrastructure Node
**25 tests** passed. Python Ruff lint, runtime/probe/test formatting, PowerShell
parsing and Git whitespace checks passed. Core has no separate configured lint
task. Existing upstream/compiler warnings remain. One transient Windows10053 in
the synthetic503 server was traced to its unread POST body; the fixture now
drains it and sends explicit empty content length. Full rerun passed. A TTS
initialization probe503 before readiness is retained/excluded; ready initialization
took90.9s. Neither result is counted as a successful latency sample.

Final seven services are ready. Unrelated Docker databases stayed running. No
helper reload, WSL reset or host reboot was performed. Gateway remains separate:
last database heartbeat2026-08-28, zero recent arrivals, protected configuration
unreadable to the SSH user and no passwordless sudo. Journal success is not local
Core acceptance; privileged destination/credential-preserving diagnosis remains.

Rollback: protected `voice-boundary/previous-{core-lan,settings}.json` retain the
previous2560AE86… V39 pin. During a quiet window stop only the reviewed managed
Core, restore those JSON files and restart through the guarded launcher. No SQL
rollback is needed. AI prior files are in `voice-boundary/rollback/`; restore
them and restart scoped AI/TTS if necessary. Satellite prior client and config
hash are in `/home/flodinho/.local/share/kyrion/voice-satellite/src/rollback-boundary-20261031-141510`;
stop its user unit, restore that module and start it. Preserve all credentials,
voice/model assets, persistent data and the prior immutable JAR.

## Immediate on-site check (still open)

1. With the normal Satellite unit active, say **“Hey Velora”**, then ask why the
   sky is blue. Listen through all sections: intelligibility, volume, complete
   word endings, pauses and answer quality. End the session.
2. Say **“Hey Velora”** again and ask for three ways to save water. Judge list
   transitions and verify that no earlier answer is replayed. Try interruption
   and record what happens. Batch mode does not currently listen concurrently
   during synchronous playback: spoken barge-in is not implemented/accepted.
3. Use the existing single-device stopwatch/video method: mark actual speech end
   and first **heard substantive answer**, excluding greetings/processing audio.
   A60fps recording gives roughly17ms frame granularity; keep it local. Compare
   these acoustic values separately with the Pi/Core trace, without subtracting
   unsynchronized absolute clocks.

For a controlled operator interruption, use
`Invoke-VeloraProbe.ps1 -Mode manual -Play -InstalledClient -AbortDuringPlayback`:
hear the greeting, speak after `READY_FOR_GERMAN_SPEECH`, then observe the
deliberate303ms-class player termination. This does not test spoken cancellation.
No person supplied observations, so human wake, audible continuity/latency and
interruption quality remain open. Real cloud acceptance/spending and V40 rollout
remain separately unauthorized.
