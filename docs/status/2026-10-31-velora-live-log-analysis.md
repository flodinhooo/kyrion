# Live Velora dialogue log analysis, 2026-10-31

Owner reports convincing audible responses, no apparent ending, and an error
after the first attempt. This continuation inspected logs, installed configuration
and session metadata only. No model, voice, schema, runtime or service changed.

## Correlated observations

Pi journal timestamps below are local CET. User-unit entries are readable via
`journalctl _SYSTEMD_USER_UNIT=kyrion-voice-satellite.service`; `journalctl --user`
reports no journal files for this SSH account. Do not mistake that for no logs.

-17:41:54: wake detected, score0.979. First turn
  `777ad2bb-1e26-457e-b208-0b4cf269b629` finishes with Core `published.completed`
  and Pi `Voice turn transcribed and answered` at17:42:28.
- A further capture/turn `d9207d35-0be7-4e65-be84-155c557c4716` finishes at
  17:42:47. Whether this was intended follow-up speech or an unintended capture
  cannot be determined from event metadata alone.
-17:42:50–51: another short capture, turn
  `c86fae65-cb2f-4776-8d60-e77737af256f`, receives an empty STT result.
  Core raises `VoiceAudioInvalidException`; Pi reports
  `Core voice stream ended before completion` and resumes wake detection.
-17:44:43: wake detected again, score0.589. Turn
  `2f77f819-1719-43d4-b536-5ff107b683cc` publishes all three answer sections
  and `completed`; Pi finishes playback/turn at17:45:25.
-17:45:28: turn `03023d9e-f1f8-4176-9f77-cf0b98aa7200` repeats the empty-STT
  failure immediately after a fresh short capture.

The failed inputs are76844 and74284 bytes, consistent with mono16kHz PCM16
containers of2.40/2.32s including silence. STT HTTP calls returned200, and Core
completed the STT phase in~602/619ms. The active binary's matching V39 source,
`VoiceDialogueController.kt:130`, throws specifically when the trimmed STT text
is blank. Neither failed turn reaches model/context processing or answer TTS.
This is not the earlier h2c422 problem or an observed model/TTS failure.

Read-only active DB inspection confirms both sessions are **closed**, reason
`error` (16:42:50.296603Z and16:45:28.270362Z). The Satellite stayed active,
`NRestarts=0`; its exception handler returns to wake detection without a systemd
restart. There is no evidence here of an indefinitely open Core session.

## Why no apparent ending, and what failed

The current batch dialogue intentionally listens for a follow-up after each
ordinary answer (`continueSession=true`). It does not audibly announce the end
of every response or an inactivity close. Installed settings: speech-start
timeout6s, end silence2s, maximum utterance20s. With no detected speech it should
close silently after the6s start timeout.

Here VAD accepted another short input instead. A single positive80ms input frame
(any positive20ms WebRTC subframe) starts an utterance; no minimum speech duration
is required. Both failed WAV lengths are consistent with a brief trigger plus
the configured2s silence tail. Background sound, reverberation or unintended
speech are plausible triggers, **not proven** without the original audio/VAD
trace. No private recording was collected or persisted for this investigation.

The definite product defect is empty-recognition handling inside an already
started response stream: it throws instead of returning an explicit recoverable
no-speech/error outcome. The client correctly refuses to treat an incomplete
stream as successful, then closes the session. The resulting generic exception
does not tell the user that no speech was understood, and the return to idle is
not audible. This explains the logged error and missing clear ending; it does
not establish the acoustic cause of the VAD trigger.

Recommended focused follow-up: a typed empty-STT stream outcome with deliberate
session policy and client feedback, plus bounded/minimum-speech VAD handling if
reproduced. Verify no LLM invocation/usage for empty input, normal inactivity,
follow-up dialogue, session cleanup and reconnect. Do not change VAD thresholds
or add a closing sound based solely on this metadata analysis. Any Core fix must
remain V39-compatible and match master; spoken barge-in remains separate.

## Result and limits

Actual wake detection and owner-heard output now have live evidence. Full
physical acceptance is still incomplete: the exit path failed in both attempts,
and complete heard list endings, precise acoustic latency and interruption were
not independently assessed. All seven services are currently ready. No live
reproduction, paid/cloud call, migration, deployment or restart was performed.
This is a documented diagnosis, not a deployed fix. Only documentation changed;
Git whitespace verification is the relevant check.
