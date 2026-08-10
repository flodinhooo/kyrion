# Streaming TTS spike acceptance criteria

These criteria apply to future local streaming-TTS candidates before any
provider is selectable in Kyrion or connected to Core. They prevent early
first PCM from hiding a runtime that cannot keep playback continuously fed.

## Immutable comparison basis

Every candidate uses the provider-independent `velora-f` reference manifest,
audio, transcript and checksum. Conditioning is prepared once and the model is
warmed before measured runs. At minimum, three warm repetitions cover:

- short DE: `Ich bin Velora.`;
- DE domain command: `Velora, schalte bitte die desk lamp im Gamingraum ein.`;
- EN domain command: `Velora, turn on the desk lamp in the gaming room, please.`;
- the existing medium and long Velora benchmark texts;
- silence-free punctuation and number cases likely to expose prosody errors.

Outputs remain private outside Git. The same texts, seeds where supported,
reference checksum, hardware load and measurement clocks are recorded.

## Hard gates

A candidate fails if any hard gate fails:

| Area | Required result |
| --- | --- |
| True incrementality | PCM is observable before generation completes; pre-splitting a batch WAV does not count. |
| First playable PCM | Warm P95 at most 2.0 s from usable phrase text; target at most 1.0 s. |
| Continuous playback | After the accepted 320 ms Satellite prebuffer, simulated buffer depth never reaches zero in any warm medium or long run. |
| Sustained throughput | Warm long-form generation RTF below 0.90, including all decoding needed for emitted chunks. |
| Chunk delivery | No update arrives later than its preceding playable audio duration plus 100 ms; no chunk exceeds the shared contract limit. |
| Cancellation | P95 at most 250 ms across early, middle and late cancellation; no later PCM and no stale queued phrase. |
| Correctness | Ordered PCM, exact declared format/rate/channels, explicit terminal, bounded queues and turn/phrase scope. |
| Stability | Twenty sequential warm turns plus cancellations show no increasing RAM/VRAM allocation, deadlock or runtime restart. |
| GPU budget | Measured TTS peak leaves at least 1 GiB physical VRAM headroom in the intended concurrent LLM profile. |
| Licence | Model, code and voice-cloning use are documented and compatible with the intended local distribution before integration. |

## Weighted listening gate

Aggregate waveform similarity cannot replace direct listening. The owner
compares full or provider reference output with streamed assembly without
provider labels. Scoring weights product identity more heavily than generic
naturalness:

| Dimension | Weight |
| --- | ---: |
| Velora voice identity and stability | 5 |
| `Velora`, room and device-name pronunciation in DE/EN | 5 |
| Boundary continuity: no click, jerk, pause or timbre jump | 5 |
| Meaning, numbers and language correctness | 3 |
| General naturalness and prosody | 2 |

Every five-weight dimension must pass every canonical phrase. Minor individual
preference may be recorded as future polish only when intelligibility, identity
and continuity pass. A single reproducible technical boundary artifact fails
the candidate configuration.

## Decision rule

Integration requires all hard gates, all critical listening dimensions and a
clear practical improvement over the operational Chatterbox batch fallback.
Passing only TTFA, average RTF or subjective voice quality is insufficient.
Failed configurations are documented and frozen rather than tuned indefinitely.

Only after acceptance may a separate slice add a provider adapter to the AI
application. Core routing, Satellite transport and fallback replacement remain
later, independently reversible gates.
