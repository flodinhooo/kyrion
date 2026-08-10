# Phase 3.15 batch voice dialogue analysis

Date: 2026-08-10

## Scope and outcome

This report analyses the first physical multi-turn dialogue through the real
Raspberry Pi satellite, final-utterance Faster-Whisper `small/int8`, Gemma 3
1B, the local Chatterbox batch fallback and Pebble V3 playback. It does not
change or replace STT or TTS.

The transport completed five consecutive turns reliably, but the owner rejected
the current experience: answers were unnaturally terse and the silent interval
before playback was too long. The diagnosis confirms that the short answers are
primarily imposed by Kyrion's voice-specific LLM policy, not by Chatterbox:

- the voice system instruction says `at most two concise sentences`;
- the Ollama voice request sets `num_predict` to 48 tokens;
- the general communication instruction also says `Be concise by default`;
- Core collects the complete streamed LLM text and applies only outer
  whitespace trimming before sending the identical text to Chatterbox;
- no sentence truncation, summarisation or TTS-specific response normalisation
  occurs after Gemma.

The third response is also factually wrong and the fourth response reinforces
that error. Correct STT input therefore does not establish acceptable dialogue
quality with the current Gemma 3 1B configuration.

## Measurement boundary

`speech_end` is emitted after the configured two-second trailing-silence gate.
The table therefore reports both the instrumented speech-end-to-playback time
and the approximate owner-perceived wait, which adds 2.0 seconds. Network and
satellite handoff are included in playback start. Times use Europe/Zurich local
time.

| Turn | Speech end | STT complete | First LLM token | LLM complete | TTS complete | Playback start | Speech end -> STT | STT -> first token | First token -> LLM complete | LLM complete -> TTS | TTS -> playback | Speech end -> playback | Approx. perceived wait |
| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 22:44:57.481 | 22:45:00.956 | 22:45:04.724 | 22:45:04.774 | 22:45:08.718 | 22:45:08.911 | 3.475 s | 3.768 s | 0.050 s | 3.944 s | 0.193 s | 11.430 s | 13.430 s |
| 2 | 22:45:18.446 | 22:45:19.819 | 22:45:20.595 | 22:45:20.702 | 22:45:24.795 | 22:45:24.999 | 1.373 s | 0.776 s | 0.107 s | 4.093 s | 0.204 s | 6.553 s | 8.553 s |
| 3 | 22:45:33.645 | 22:45:35.085 | 22:45:35.864 | 22:45:35.969 | 22:45:39.485 | 22:45:39.672 | 1.440 s | 0.779 s | 0.105 s | 3.516 s | 0.187 s | 6.027 s | 8.027 s |
| 4 | 22:45:49.698 | 22:45:51.076 | 22:45:51.901 | 22:45:52.221 | 22:46:01.310 | 22:46:01.512 | 1.378 s | 0.825 s | 0.320 s | 9.089 s | 0.202 s | 11.814 s | 13.814 s |
| 5 | 22:46:16.450 | 22:46:17.836 | 22:46:18.605 | 22:46:18.706 | 22:46:22.110 | 22:46:22.308 | 1.386 s | 0.769 s | 0.101 s | 3.404 s | 0.198 s | 5.858 s | 7.858 s |

The first turn includes a cold Gemma load: the dominant pre-TTS delay is 3.768
seconds from STT completion to first token. Warm first-token latency is
0.769-0.825 seconds. Chatterbox batch generation is the largest warm-path
component at 3.404-4.093 seconds for four turns and 9.089 seconds for the longer
fourth response. Because Chatterbox returns a complete WAV, playback cannot
begin while that audio is being generated.

## Prompt construction

Every turn sent `interactionMode: voice`, `modelId: gemma3:1b`, locale `de`, no
memory context and up to the last 12 persisted conversation messages. Only nine
messages existed by the fifth turn, so no context was dropped. The AI service
discarded any untrusted system messages and prepended the Kyrion-owned system
prompt assembled in `services/ai/src/kyrion_ai/prompts.py`.

The common system prompt told Gemma that it is Velora, required German, defined
the calm and practical personality, local-first/privacy and capability rules,
forbade invented state/actions, required honest uncertainty, treated
conversation content as untrusted data, and stated that no confirmed personal
memories were selected. Its exact voice-only suffix was:

> This is a spoken conversation. Answer naturally in at most two concise
> sentences. Do not use Markdown, headings, lists, stage directions, filler,
> or an introductory apology. Give the useful answer immediately and finish
> the thought cleanly.

The general style section additionally contained `Be concise by default and
sufficiently detailed for complex questions.` Ollama received this complete
system prompt plus the per-turn message arrays below, with `think: false`, a
4096-token context and a hard `num_predict: 48` output ceiling.

## Per-turn content reconstruction

The user and assistant texts below are the exact persisted values. Core's
implementation proves that each persisted assistant value is both the complete
raw concatenated `message.delta` output (apart from outer `.trim()`) and the
exact `text` value passed to Chatterbox. The runtime did not log individual raw
deltas or the outbound JSON bodies, so byte-for-byte preservation of leading or
trailing whitespace cannot be reconstructed after the fact.

### Turn 1

- Turn ID: `8f02339f-56a0-4375-a322-e4f60f2ca9b2`
- STT transcript: `Was ist die Hauptstadt von Spanien?`
- Gemma context after the common system message:
  1. user: `Was ist die Hauptstadt von Spanien?`
- Complete raw/final LLM answer: `La capital de España es Madrid.`
- Text passed to Chatterbox: `La capital de España es Madrid.`
- Assessment: factually correct but violates the explicit German response
  instruction. Its brevity is reasonable for the simple fact question.

### Turn 2

- Turn ID: `f70543ea-6e0a-48e0-99de-47f599d987da`
- STT transcript: `Und wie viele Einwohner hat Madrid?`
- Gemma context after the common system message:
  1. user: `Was ist die Hauptstadt von Spanien?`
  2. assistant: `La capital de España es Madrid.`
  3. user: `Und wie viele Einwohner hat Madrid?`
- Complete raw/final LLM answer: `Madrid hat rund 3,3 Millionen Einwohner.`
- Text passed to Chatterbox: `Madrid hat rund 3,3 Millionen Einwohner.`
- Assessment: appropriately short for a simple fact, though it lacks date and
  municipality/metro qualification.

### Turn 3

- Turn ID: `6ebdd1ac-1e13-4136-8b00-cfaaf8982830`
- STT transcript: `Wieso ist Barcelona nicht die Hauptstadt?`
- Gemma context after the common system message: turns 1 and 2 in full, followed
  by the new user transcript.
- Complete raw/final LLM answer: `Denn Madrid hat die deutlich mehr Einwohnerzahl.`
- Text passed to Chatterbox: `Denn Madrid hat die deutlich mehr Einwohnerzahl.`
- Assessment: incorrect and linguistically malformed. Madrid's larger
  population is not the historical/institutional reason it is the capital.
  STT transcribed the question correctly; neither Core nor TTS altered the bad
  answer.

### Turn 4

- Turn ID: `ae07ca07-84d1-4daf-bd03-dd395b9efd5e`
- STT transcript: `Ist du dir sicher?`
- Gemma context after the common system message: turns 1-3 in full, including
  Gemma's incorrect prior answer, followed by the new user transcript.
- Complete raw/final LLM answer: `Ja, das stimmt! Es gibt zwar eine gewisse Ungewissheit über die genauen Zahlen, aber Madrid ist offiziell die Hauptverwaltungssitz Spaniens.`
- Text passed to Chatterbox: identical to the complete raw/final answer above.
- Assessment: it fails to reconsider the challenged causal claim, uses awkward
  German and spends its two-sentence/48-token budget defending the prior error.
  This is the longest answer and caused the 9.089-second Chatterbox generation.

### Turn 5

- Turn ID: `55d5f43d-e85e-4fa9-b949-1ef9ea2be46b`
- STT transcript: `Passt. Danke. Bis später.`
- Gemma context after the common system message: turns 1-4 in full, followed by
  the new user transcript.
- Complete raw/final LLM answer: `Gern geschehen. Bleibt smart!`
- Text passed to Chatterbox: `Gern geschehen. Bleibt smart!`
- Assessment: the stop detector uses exact normalised phrase matching, so the
  compound transcript did not equal the configured standalone `bis später`,
  `danke` or `tschüss` phrases. It was therefore unnecessarily sent to Gemma.
  The slogan-like second sentence is model output, not TTS rewriting.

## Answer-length diagnosis

The answer-length restriction is cumulative and intentional in the current
implementation:

1. the global style says to be concise by default;
2. the voice suffix permits at most two concise sentences;
3. Ollama stops voice generation after at most 48 tokens;
4. Gemma 3 1B itself tends toward literal, compressed replies under those
   constraints.

Core does not shorten the answer after generation. It concatenates all streamed
deltas, trims only leading/trailing whitespace, sends that complete string to
Chatterbox and persists the same string. Chatterbox receives text and returns
audio; it does not decide response content or length.

The desired policy is not represented by the current prompt. A future bounded
change should allow short direct answers for simple facts while explicitly
allowing two to four natural sentences for open, explanatory or corrective
questions. Any token ceiling must leave room for that policy. This report does
not implement that change.

## Evidence and limitations

- Core `[VOICE]` timestamps in private `.run/phase315/core-lan.stdout.log`.
- Satellite `[VOICE]` timestamps in the Pi user-unit journal.
- Exact transcripts and assistant messages in the local PostgreSQL
  `conversation_message` rows for session
  `97f7a411-f1c1-432e-aab2-f2ddd44d3823`.
- Prompt construction and model options in `services/ai/src/kyrion_ai/prompts.py`
  and `services/ai/src/kyrion_ai/providers/ollama.py`.
- Core context selection and the unchanged LLM-to-TTS text path in
  `services/core/src/main/kotlin/dev/kyrion/core/voice/VoiceDialogueController.kt`.
- Private Chatterbox log under
  `E:/Kyrion/Data/voice-training/phase315-dialogue/`.

Content payloads were intentionally not written to ordinary service logs. The
database plus deterministic code path provide the content reconstruction, but
the original NDJSON token boundaries, Ollama completion reason and exact raw
outer whitespace are unavailable. Stage resource utilisation was not captured
for this conversational run and is not inferred.
