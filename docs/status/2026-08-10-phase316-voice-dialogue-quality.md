# Phase 3.16 voice dialogue quality

Date: 2026-08-10

## Scope

Phase 3.16 changes only the existing batch dialogue's LLM response policy and
deterministic session-end recognition. Faster-Whisper, Chatterbox, the TTS
benchmark, Voice transport, PCM handling and Raspberry Pi Satellite
infrastructure are unchanged.

The physical before-state and its five turn measurements are preserved in the
[Phase 3.15 analysis](2026-08-10-phase315-batch-voice-dialogue-analysis.md).

## Before and after

| Concern | Phase 3.15 | Phase 3.16 implementation |
| --- | --- | --- |
| Simple fact | General brevity plus at most two concise sentences | Normally one or two natural sentences |
| Ordinary question | Same hard two-sentence policy | Typically two to four natural spoken sentences |
| Explanation or correction | Artificially constrained even when information was lost | May be longer when accuracy, completeness or naturalness requires it |
| Doubt or contradiction | No dedicated instruction; Gemma reflexively confirmed its prior Madrid error | Explicitly re-check the relevant claim rather than reflexively confirming it |
| Voice output bound | `num_predict: 48` | `num_predict: 256` |
| Natural session end | Exact match against one complete normalised phrase | Deterministic terminal phrase plus restricted acknowledgement/politeness prefix |

The adaptive Voice policy, rather than the token ceiling, controls normal
answer length: simple facts should remain short, ordinary questions should
usually receive two to four sentences, and only explanations or corrections
may run longer when necessary. `num_predict: 256` is deliberately a generous
upper safety bound for exceptional spoken answers, not a target length. It
still prevents unbounded local generation and downstream batch-TTS input. A
dynamic semantic token budget would add complexity without an accepted
measurement demonstrating that it is necessary.

Voice output still forbids Markdown, headings, lists, stage directions,
introductory apologies and unnecessary filler. It must answer directly and
sound natural when spoken.

## Session-end recognition

Core now strips punctuation, case and diacritics, then recognises a small set of
terminal word sequences only when all preceding words belong to a restricted
acknowledgement/politeness vocabulary. This accepts utterances such as:

- `Bis später.`
- `Danke, bis später.`
- `Passt. Danke. Bis später.`
- `Okay, tschüss.`
- `Danke dir, das war's.`

It rejects contextual or quoted mentions such as `Sag mir, was 'bis später'
bedeutet.` and `Wie sagt man tschüss auf Spanisch?`. This is intentionally a
small deterministic intent recogniser, not an LLM call or unrestricted
substring match.

## Regression coverage

AI tests cover the adaptive spoken-answer policy, the 256-token safety-bounded Ollama
payload, simple facts, a contextual follow-up, an open explanation, the
Madrid/Barcelona doubt scenario and a user correction. These tests assert
prompt policy and preservation of conversation context, not an exact
non-deterministic model answer.

Core parameterised tests cover natural German/English session endings,
punctuation and ASCII spelling variants, plus negative quoted/contextual
mentions. The first run exposed a missing `spaeter` variant; it was added and
the complete suites then passed.

Verification:

- AI Ruff: passed;
- AI pytest: 79 passed;
- Core Gradle tests: 55 passed;
- physical after-run: pending owner-ready checkpoint.

## Physical after-run plan

Use the same Pi, Delock microphone, Pebble V3, two-second silence gate,
Faster-Whisper `small/int8`, Gemma 3 1B and Chatterbox batch path as Phase 3.15.
After an explicit sound warning, run one session:

1. wake word and greeting;
2. `Was ist die Hauptstadt von Spanien?`
3. `Und seit wann ist Madrid die Hauptstadt?`
4. `Warum ist Barcelona nicht die Hauptstadt?`
5. `Bist du dir sicher? Prüfe deine vorherige Begründung bitte noch einmal.`
6. `Okay, danke dir, bis später.`

For every turn, reconstruct the exact persisted STT transcript, full LLM answer
and identical Chatterbox input. Combine Core and Satellite timestamps for
speech-end to STT completion, STT completion to first token, total LLM time,
TTS time, playback start and perceived total latency including the silence
gate. Compare the after-run directly with the Phase 3.15 table. Do not log
private conversation content into ordinary service logs merely for this test.
