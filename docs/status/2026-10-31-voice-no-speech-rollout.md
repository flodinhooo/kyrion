# Empty recognition: tested local V39 activation

Continuation from master `387be3b`, active V39 `2488c1b` and the
[live error diagnosis](2026-10-31-velora-live-log-analysis.md). The owner explicitly
authorized implementing and activating this fix for a repeat physical test.

## Behavior and bounded scope

Core now closes an authenticated session with reason `inactivity` when STT returns
blank/whitespace, then publishes exactly one terminal `completed` event:
`outcome: "no_speech", continueSession: false`. It does not create a conversation
turn, reserve model usage, call actions/model/TTS or invent an answer. The new
outcome is optional on ordinary events, preserving their existing wire shape.

The installed batch client accepts empty text only for this explicit terminal
outcome. Inconsistent text/audio/pending-action/restart results still fail; absent
or truncated completion is not success. DialogueRunner logs the no-speech exit,
returns to idle without retry, and does not re-close the already closed session.
Normal answered turns still allow a follow-up; ordinary capture inactivity still
closes once. No VAD threshold, minimum speech length, voice, model, TTS engine,
cloud policy, accounting schema or permission boundary changed.

The acoustic cause of the previous brief VAD captures is still unproven. This
fix handles their **empty recognition result**, not every possible noise trigger.
Inactivity/no-speech closure remains silent: no farewell sound or spoken barge-in
was added. Human testing should check return to wake readiness, not wait for an
unimplemented audible ending.

## Tests and actual active artifacts

- Full Core tests and `bootJar`, offline dependencies: **315 master /296 V39**,
  no failures/errors/skips. The new HTTP-backed service regression supplies
  whitespace recognition and verifies one close/completion, no actions, model,
  response policy/audio or conversation persistence interactions.
- Satellite full suite: **77 passed**; no-speech terminal parsing, rejection of
  missing/inconsistent results, no repeated close/retry, and ordinary
  answer→follow-up→inactivity are covered. Ruff lint/format passed. Existing
  Kotlin/Gradle deprecation warnings remain; no separate Core lint task exists.
- New V39 compatibility commit: **`f07c20a`**, branch
  `fix/core-v39-voice-compat`. The same Core fix/test is on master. No migration
  was altered, removed from a build or applied to the active DB.
- Pinned artifact: `.run/dev-recovery/no-speech/core-runtime.jar`, SHA256
  **`D023441F034B79E0E5D8F6F40194E844DBDF0074BA259C080BB56D5C04784D5B`**.
  Protected pin/settings updated in place; ACLs retained. `Start-CoreLan -ValidateOnly`
  verified LAN/firewall guards and exact39-migration compatibility, no checksum
  mismatch/pending migration/active Calendar lease. There were no active Voice
  sessions before restarting.
- Existing authenticated loopback helper performed only scoped Core restart,
  correlation `263567da-cc12-4d76-aa17-d985c15942a0`; no helper reload or broad restart.
  Actual Core PID18596 uses immutable copy
  `.run/dev-recovery/guarded-start-5d6edf21-4d3c-40d3-b213-add90c184d27/core-runtime.jar`,
  same hash, LAN bind and guards verified.
- Satellite0.1.0: only `core_client.py` and `dialogue.py` updated in the installed
  package. SHA256 respectively
  `6904f68bdd1b53213d1d43f5dde22d41f3880552404aed6d9d2fddbe19abb962` and
  `b30367c3eb1ab9e92f0ddbc5b370e9237307ff214ddcce30a2b97800c75b72a1`.
  Configuration SHA256 stayed
  `22cbb2b653d5a8e7017bb7d15b51c5d9f71feccb09cff74dcc9cff94e3e0ed92`;
  credentials untouched. Only that user unit was stopped/started. It is active
  again after the software acceptance tests.

## Real local regression checks

1. From Pi, the installed authenticated client submitted a generated1s PCM16
   silence WAV to the actual running Core/STT. Turn
   `e2cb12fb-a289-4352-aa40-7f2bc36a8c26` returned `no_speech`, no audio, no text,
   no retry, no exception. DB session `527a3d13-e987-4dcc-b730-5018fe4d914b` is
   closed/inactivity with **zero messages and zero linked model usage attempts**.
   No microphone recording was made.
2. Existing synthetic Q1 fixture went through installed Pi client→STT→local
   Gemma→Chatterbox→Pi playback. Turn `794c9522-648c-420e-b19f-cfb77d5ed28f`
   completed two valid answer sections (5.12/6.16s), playback and session closure.
   DB: one user/assistant pair, one `reported` usage attempt (987 input/41 output
   tokens), session closed/explicit. Retained ignored evidence:
   `.run/dev-recovery/no-speech/normal-dialogue.jsonl`.
3. That fixture's final transcript correctly contained `Warum ist der Himmel blau?
   Antworte in zwei kurzen Sätzen.` The generated response had two sentences.
   This demonstrates this input, not guaranteed recognition or identical outputs
   for every wording. First answer Pi receipt11.977s from fixture request start;
   software playback completed26.248s. These are not acoustic measurements or a
   new speed comparison. The microphone/wake path was not exercised by the fixture.
4. After unit restoration, Pi DNS/TCP/health, unauthenticated401, all three Pi
   user units and all seven local services were ready. Schema remains39.

## Repeat with a person

The active fix is ready. Say **Hey Velora**, wait for greeting, then:

1. `Warum ist der Himmel blau? Antworte in höchstens zwei kurzen Sätzen.`
   Hear the complete answer, then remain quiet for at least10s.
2. Say **Hey Velora** again, wait for greeting, ask
   `Nenne drei Möglichkeiten, Wasser zu sparen.` Hear all items, then stay quiet
   for at least10s again. Report missing endings, pauses, unexpected further
   responses or errors; no farewell sound is expected on inactivity closure.

The full recognized request is stored as the user turn and passed through the
existing context/model path. Brevity instructions can change response form/length;
they are not stripped or an exact-output contract. `Fasse es zusammen` also uses
available conversation context, so explicit `Antworte in höchstens zwei kurzen
Sätzen` is less ambiguous for the first question. Recognition remains dependent
on real microphone conditions. No unrequested model/voice change was introduced.

## Rollback and remaining gates

Previous pin/settings are retained in
`.run/dev-recovery/no-speech/previous-{core-lan,settings}.json`; the prior
50A8174C… JAR remains intact. In a quiet window stop only the Satellite, restore
those two JSON contents preserving ACLs, scoped-restart Core through the helper,
restore both Satellite modules from
`/home/flodinho/.local/share/kyrion/voice-satellite/src/rollback-no-speech-f07c20a`,
then start its unit and repeat health/auth checks. Do not reset Docker or change
SQL. Configuration, enrollment/credentials and prior model/voice assets remain.

Physical silence-after-answer regression remains for the owner. Prior A/B voice
decision stays Chatterbox. Spoken interruption, Gateway privileged diagnosis,
full-host restart proof, paid cloud acceptance and V40 rollout remain separate.
No cloud spending, public deployment, WSL/host restart or persistent-data deletion
occurred; Calendar and foreign work stayed untouched.
