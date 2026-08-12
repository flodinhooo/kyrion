# Kyrion/Velora Voice MVP handoff

Date: 2026-08-12

This is the canonical continuation document for the current Voice work. A new
chat should read this file first, followed by `AGENTS.md`, the root `README.md`,
ADR 0010 and the linked detailed reports. Later decisions in this document
supersede older open investigation items where they conflict.

## Executive state

- The provider-neutral Fixed/Template/Dynamic response architecture is
  implemented.
- There is **no accepted dedicated dynamic Short-TTS provider**.
- Dedicated Short-TTS discovery is paused. Do not start another provider search
  or download in the Voice MVP lane.
- XTTS v2 remains experimental/opt-in and a quality reference for normal and
  longer responses. Its Short EOS/VAD/guard/punctuation/termination work is
  closed and must not be reopened.
- No Fixed Velora production WAV is approved or registered. The manifest has
  `0` assets and `12` pending assets.
- Twelve XTTS-generated review candidates exist outside Git. Owner review has
  rejected eight, left four unreviewed and accepted none.
- The immediate next step is a sound-engineering discussion and creation of
  twelve high-quality reviewed recordings, not more TTS research.
- Core command authority, provider routing and the Fixed/Template/Dynamic
  architecture must remain unchanged while completing the assets.

## Implemented architecture

Core owns response meaning and creates a typed `VoiceResponsePlan` from trusted
provenance:

- Category A / Fixed: registered response key and deterministic variant;
- Category B / Template: registered localized template plus validated typed
  slots from trusted Core state;
- Category C / Dynamic: ordinary unrestricted response text.

The AI service resolves an already validated plan to audio:

- Fixed plans first look up checksum-pinned reviewed WAVs in
  `services/ai/voice-responses/manifest.json`;
- a missing pending Fixed asset uses the existing stable NormalTtsFallback and
  reports `fixed_asset_pending_review`;
- Template plans use a revision-safe, owner-scoped, content-addressed cache of
  complete utterance WAVs;
- a Template cache hit returns the stored complete WAV immediately;
- a Template cache miss uses the existing `http_batch` NormalTtsFallback once
  and stores the validated complete WAV;
- Dynamic plans use the existing normal provider-neutral TTS path unchanged.

There is no text-length heuristic. The LLM cannot establish command success or
supply arbitrary templates/slots. XTTS is not the semantic router.

Primary implementation:

- `services/core/src/main/kotlin/dev/kyrion/core/voice/VoiceResponsePlan.kt`
- `services/core/src/main/kotlin/dev/kyrion/core/voice/VoiceDialogueController.kt`
- `services/ai/src/kyrion_ai/voice_responses.py`
- `services/ai/src/kyrion_ai/app.py`
- `services/ai/voice-responses/manifest.json`
- `services/voice-satellite/src/kyrion_voice_satellite/core_client.py`
- `services/voice-satellite/src/kyrion_voice_satellite/dialogue.py`

Durable decision: [ADR 0010](../adr/0010-core-owned-typed-voice-response-plans.md).

## Implemented live batch Voice flow

The current Raspberry Pi batch path is:

1. Satellite opens an authenticated Voice session.
2. Satellite requests `session.greeting` from Core.
3. Core resolves a Fixed greeting plan and the AI service returns either the
   reviewed manifest asset or the existing fallback while it remains pending.
4. Satellite plays the greeting and begins listening.
5. Core transcribes the captured WAV with the explicit DE/EN locale.
6. After a valid non-terminal transcript, Core emits a Fixed
   `dialogue.acknowledged` response. This acknowledges successful capture/STT;
   it is not selected by the LLM.
7. Ordinary dialogue continues as Category C through chat and normal TTS.
8. A deterministically recognized session ending emits Fixed
   `session.farewell`, skips acknowledgement, returns
   `continueSession=false` and closes the session.

The Satellite's configured local `greeting_audio_file` remains only a
compatibility fallback when Core greeting resolution fails.

Core validates returned greeting/response audio as bounded RIFF/WAVE before it
is sent. The Satellite also validates server-resolved greeting audio.

## Command templates and deliberate boundary

`command.succeeded` and `command.failed` are registered in DE/EN and resolve to
Category-B Template plans with a validated `entityName` slot. Cache behaviour
is implemented and tested.

They are **not yet spoken by the live Voice controller** because that controller
does not execute a device command and does not receive the authoritative
`DeviceCommandResult`. Do not infer success from LLM text and do not add a
second command-execution path. A later slice may connect the templates only
when the real Core-confirmed result and correlation ID are available in the
Voice orchestration.

## Short-TTS research closure

Final candidate state:

| Candidate | State | Reason |
| --- | --- | --- |
| Piper | C / eliminated | Very fast, but owner rejected quality and Velora identity. |
| Chatterbox | C / eliminated | Owner rejected quality/identity; Short latency also unacceptable. |
| Qwen 0.6B/1.7B | C / eliminated for this path | Strong voice samples, but latency, sustained streaming and resource/custom-runtime constraints. |
| CosyVoice3 0.5B | C / eliminated | 4.2–5.4 s first PCM and usually one complete chunk. |
| MOSS-TTS-Nano | Not accepted; lane closed | Warm synthesis roughly 1.9–2.5 s, mean RTF about 1.25; no exposed playable TTFA through tested API. |
| Zonos v0.1 | Research-only | Not downloaded; official hardware target is newer than the available RTX 2070. |
| XTTS v2 | Normal/long experimental reference | Excellent longer-form quality, but no reliable dynamic Short completion signal. |

F5-TTS, Fish Speech, Kokoro, OpenVoice V2 and NeuTTS were rejected before
benchmark/download for the documented language, cloning, licence or deployment
gaps. Do not force a winner from prior results.

Detailed evidence:

- [Short-TTS provider benchmark](2026-08-11-short-tts-provider-benchmark.md)
- [XTTS multi-signal guard decision](2026-08-11-xtts-v2-multisignal-code-guard.md)
- [XTTS Short follow-up](2026-08-11-xtts-v2-short-output-follow-up.md)

## Fixed response inventory

All final assets must be mono RIFF/WAV, PCM16, 24 kHz and manually approved.

| Order | Target path under `services/ai/voice-responses/` | Exact text |
| ---: | --- | --- |
| 1 | `assets/velora/de/session.greeting/neutral-01.wav` | `Hallo.` |
| 2 | `assets/velora/de/session.greeting/warm-01.wav` | `Hallo, schön dich zu hören.` |
| 3 | `assets/velora/en/session.greeting/neutral-01.wav` | `Hello.` |
| 4 | `assets/velora/en/session.greeting/warm-01.wav` | `Hello, good to hear you.` |
| 5 | `assets/velora/de/session.farewell/neutral-01.wav` | `Bis später.` |
| 6 | `assets/velora/de/session.farewell/warm-01.wav` | `Mach's gut.` |
| 7 | `assets/velora/en/session.farewell/neutral-01.wav` | `Talk to you later.` |
| 8 | `assets/velora/en/session.farewell/warm-01.wav` | `Take care.` |
| 9 | `assets/velora/de/dialogue.acknowledged/neutral-01.wav` | `Okay.` |
| 10 | `assets/velora/de/dialogue.acknowledged/neutral-02.wav` | `Alles klar.` |
| 11 | `assets/velora/en/dialogue.acknowledged/neutral-01.wav` | `Okay.` |
| 12 | `assets/velora/en/dialogue.acknowledged/neutral-02.wav` | `Got it.` |

Register an owner-approved file only with
`.run/register_fixed_voice_response_asset.py`. The script validates mono PCM16
24 kHz, copies the file into the versioned asset tree, records SHA-256 and
removes exactly the matching pending entry. Never pass `--owner-approved` before
the owner has listened to the entire WAV.

## Current Fixed candidate review

The first twelve candidates were generated with the existing stock XTTS v2 and
immutable Velora-F reference only to populate a listening gate. They are not
production assets and were not registered.

Location:

`E:/Kyrion/Data/voice-training/fixed-responses/velora/`

Metadata:

`E:/Kyrion/Data/voice-training/fixed-responses/velora/generation-results.json`

Owner result:

- rejected: 8;
- still unreviewed: 4;
- accepted: 0;
- registered: 0.

Rejected observations:

- both German greetings: fantasy speech at the ending; warm is materially
  worse than neutral;
- both German farewells: fantasy words;
- both German acknowledgements: punctuation audibly spoken as `Punkt`;
- English neutral greeting: fantasy speech at the ending;
- English warm farewell: unnatural final tone.

Still unreviewed, but not sufficient to solve the complete asset requirement:

- English warm greeting;
- English neutral farewell;
- English `Okay.` acknowledgement;
- English `Got it.` acknowledgement.

Do not trim, repair or register the failed files. Do not generate another XTTS
Short batch as an implicit experiment.

## Sound-engineering review package

A curated, non-production comparison package exists at:

`E:/Kyrion/Data/voice-training/tontechnik-velora-review/`

It contains eleven copied WAVs plus a README:

- three canonical/owner-liked references;
- three good longer XTTS examples;
- five problem examples covering fantasy speech, bad endings, unsuitable voice
  identity and repetition.

Original evidence remains untouched. The intended use is discussion with a
sound engineer about voice identity, performance consistency, loudness,
silence and recording the twelve final prompts.

## Verification checkpoint

Last completed verification after the live MVP changes:

- AI Ruff: passed;
- AI pytest: 91 passed;
- Voice Satellite Ruff: passed;
- Voice Satellite pytest: 47 passed;
- Core Voice tests: passed;
- Core `bootJar`: passed;
- complete Core suite: 56 of 57 tests passed;
- sole Core failure: Testcontainers initialization because Docker was not
  available, not an application assertion failure;
- fixed asset registration CLI compilation/help: passed;
- candidate generation produced twelve mono PCM16/24 kHz WAVs;
- manifest remains at zero registered and twelve pending assets.

Relevant commits, newest first:

- `3a80ba1` — manual Fixed candidate review and sound-engineering package notes;
- `4a18cad` — Fixed candidate generation and live greeting/acknowledgement flow;
- `3361a51` — stable Voice MVP documentation and provider-search closure;
- `8f9df7b` — Short-TTS reviews, MOSS benchmark and Fixed asset registration;
- `e45696c` — owner-scoped Template cache and stable Short fallback boundary.

## Next safe continuation

1. Discuss the curated samples with the sound engineer.
2. Decide how the twelve final lines will be performed/recorded while retaining
   the canonical Velora identity.
3. Produce review candidates outside the production asset tree.
4. Listen to every complete WAV for exact wording, clean termination, identity,
   pronunciation, prosody, loudness and leading/trailing silence.
5. Convert/verify each accepted file as mono PCM16/24 kHz without changing the
   approved performance.
6. Register accepted files one by one through the existing script.
7. Confirm manifest `pendingAssets` is empty and all hashes resolve.
8. Run the DE and EN Raspberry Pi/Pebble acceptance plan documented in
   [Stable Voice MVP](2026-08-11-stable-voice-mvp.md#raspberry-pi-satellite-acceptance).

Do not, as part of this continuation:

- change the Fixed/Template/Dynamic architecture;
- change Core or fallback routing;
- integrate another provider;
- start provider discovery/downloads;
- reopen XTTS Short optimisation;
- use per-chunk ASR, VAD-only stopping or EOS bias;
- connect command-success speech without a real Core-confirmed outcome.

## Worktree caution

At this checkpoint the Voice work is committed. The worktree contains unrelated
`apps/web` add/delete entries belonging to parallel/user work. Preserve them and
do not restore, delete or include them in Voice changes.
