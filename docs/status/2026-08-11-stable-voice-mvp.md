# Stable Kyrion/Velora Voice MVP

Date: 2026-08-11

## Outcome

The MVP uses the existing provider-neutral Fixed/Template/Dynamic architecture
without selecting another Short-TTS provider or reopening XTTS Short
optimisation.

The live batch Voice path now behaves as follows:

1. An authenticated session opens.
2. The Satellite requests `session.greeting` from Core. Core creates a fixed
   plan and the AI resolver uses a reviewed manifest asset when available.
3. After a valid non-terminal STT result, Core emits
   `dialogue.acknowledged` from a fixed plan. This is based on the observed STT
   completion, not an LLM classification.
4. Ordinary dialogue remains Category C and uses the unchanged normal,
   provider-neutral TTS path.
5. An explicitly recognised session ending emits the existing fixed
   `session.farewell` and closes the session.

The old Satellite `greeting_audio_file` is only a compatibility fallback if the
server greeting request fails. It is no longer preferred over the manifest
path.

## Category B and command boundary

The registered `command.succeeded` and `command.failed` DE/EN templates are
fully supported by the AI response resolver:

- the complete rendered utterance and trusted typed slots form the cache key;
- a cache hit returns the stored complete WAV;
- a cache miss calls the existing stable `http_batch` NormalTtsFallback once
  and stores the complete valid WAV;
- no text-length heuristic and no new provider are involved.

The current Voice controller does not execute a device command and does not
receive a `DeviceCommandResult`. Consequently, command success/failure is not
spoken in the live Voice turn yet. Connecting it without a confirmed result
would let model text imply success and violate Core authority. The next command
slice must pass the actual Core result and correlation ID into
`CommandExecutionOutcome`; it must not add a second execution path in the
Voice controller.

## Fixed-response asset pipeline

No production WAV was generated or approved in this implementation. The
manifest records the final wording for every pending asset. After the owner has
created and listened to a WAV, register it with:

```powershell
python .run/register_fixed_voice_response_asset.py `
  --manifest services/ai/voice-responses/manifest.json `
  --source E:/path/to/owner-approved.wav `
  --locale de `
  --response-key session.greeting `
  --variant-id neutral-01 `
  --owner-approved
```

The registration command accepts only mono PCM16 24 kHz WAV, copies it into the
versioned asset tree, records its SHA-256 and removes exactly that entry from
`pendingAssets`. Until an asset is approved, the existing NormalTtsFallback is
used and the resolution reports `fixed_asset_pending_review`.

## Required owner-created Velora WAVs

| File | Exact spoken text |
| --- | --- |
| `assets/velora/de/session.greeting/neutral-01.wav` | `Hallo.` |
| `assets/velora/de/session.greeting/warm-01.wav` | `Hallo, schön dich zu hören.` |
| `assets/velora/en/session.greeting/neutral-01.wav` | `Hello.` |
| `assets/velora/en/session.greeting/warm-01.wav` | `Hello, good to hear you.` |
| `assets/velora/de/session.farewell/neutral-01.wav` | `Bis später.` |
| `assets/velora/de/session.farewell/warm-01.wav` | `Mach's gut.` |
| `assets/velora/en/session.farewell/neutral-01.wav` | `Talk to you later.` |
| `assets/velora/en/session.farewell/warm-01.wav` | `Take care.` |
| `assets/velora/de/dialogue.acknowledged/neutral-01.wav` | `Okay.` |
| `assets/velora/de/dialogue.acknowledged/neutral-02.wav` | `Alles klar.` |
| `assets/velora/en/dialogue.acknowledged/neutral-01.wav` | `Okay.` |
| `assets/velora/en/dialogue.acknowledged/neutral-02.wav` | `Got it.` |

Owner review must confirm exact wording, clean termination, Velora identity,
natural prosody, consistent loudness and acceptable leading/trailing silence.

## Raspberry Pi Satellite acceptance

Run one DE session and one EN session using the physical microphone and normal
PipeWire/Pebble output:

1. Wake with `Hey Velora`; verify exactly one reviewed greeting plays before
   listening begins.
2. Ask one ordinary question; verify transcript, one reviewed acknowledgement,
   the complete dynamic answer and no overlap between the two WAVs.
3. Repeat the same registered command-template resolution twice through a
   controlled Core test outcome: verify first request logs
   `template_cache_miss` and the second logs `template_cache`/cache hit. Do not
   claim physical command success unless the real command result is supplied.
4. Say a natural DE/EN farewell; verify no acknowledgement precedes it, the
   reviewed farewell plays once, `continueSession=false`, and the session
   closes explicitly.
5. Stop the normal TTS runtime after fixed assets are deployed; verify greeting,
   acknowledgement and farewell still play, proving Category A independence.
6. Confirm Satellite logs contain one playback start per expected utterance,
   with no duplicate chunks, underruns or audio from the previous turn.

Record response mode, audio source, cache hit, fallback reason and turn/session
IDs. Do not record room audio or secrets.

## Open MVP items

- Create, listen to and approve the twelve fixed WAVs above.
- Run the physical Raspberry Pi acceptance after deploying those assets.
- Connect command templates only when the live Voice orchestrator receives an
  actual Core-confirmed command result and correlation ID.
- Define cache retention/quota policy after the MVP demonstrates real cache
  usage.
- Keep XTTS experimental/opt-in for normal and longer answers; do not use it as
  a Short-completion solution.

## Verification

- AI Ruff: passed;
- AI pytest: 91 passed;
- Voice Satellite Ruff: passed;
- Voice Satellite pytest: 47 passed;
- Core Voice test selection: passed;
- Core `bootJar`: passed;
- complete Core suite: 56 of 57 tests passed; the sole failure is the existing
  Testcontainers integration-test initialization because Docker is unavailable,
  not an application assertion failure;
- fixed-asset registration script compilation and CLI help: passed.
