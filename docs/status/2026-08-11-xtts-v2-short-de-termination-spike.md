# XTTS v2 short-DE termination spike — 2026-08-11

## Outcome

XTTS v2 remained an isolated candidate at this stage. The subsequent live
generator spike is the deciding measurement and records a no-go for integration
on the current MVP hardware; see
`2026-08-11-xtts-v2-live-generator-guard-spike.md`.

A small documented decoding matrix did not reliably fix the reproducible
post-content pseudo-speech generated for `Ich bin Velora.`. A separate offline
streaming-guard simulation did remove the tail from all six selected short
samples while leaving the existing Long-DE and Dialogue-DE controls at their
full original duration. This is promising evidence for another isolated guard
proof, not permission to integrate.

## Decoding matrix

All variants use the immutable Velora-F reference, 20-token native XTTS
streaming, three identical seeds and no text splitting. The baseline matches
the original runner. Official XTTS 0.22 documentation is inconsistent: the
`inference_stream()` implementation defaults to temperature 0.75,
repetition penalty 10, top-k 50 and top-p 0.85, while user-facing documentation
describes temperature 0.65, repetition penalty 2 and top-p 0.8. The bounded
matrix isolates repetition and length before testing the documented
lower-entropy combination.

| Profile | Temperature | Length penalty | Repetition penalty | Top-k / top-p | Durations, runs 1–3 | Result |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Baseline | 0.75 | 1.0 | 10 | 50 / 0.85 | 6.592 / 4.875 / 8.960 s | 0/3 clean |
| Repetition 2 | 0.75 | 1.0 | 2 | 50 / 0.85 | 6.176 / 4.875 / 2.923 s | not reliable |
| Length 1.5 | 0.75 | 1.5 | 10 | 50 / 0.85 | 6.592 / 4.875 / 8.960 s | identical to baseline |
| Documented conservative | 0.65 | 1.0 | 2 | 50 / 0.8 | 2.091 / 8.960 / 2.272 s | not reliable |

TTFA remains 0.514–0.659 seconds, RTF 0.597–0.777 and every run has zero
buffer underruns. Faster-Whisper and -45 dBFS activity measurement confirm
post-content signal in every profile. Conservative outputs still add `Und?`,
`Bernden` or a longer invented phrase. The length-penalty result is bit-length
identical by seed to baseline; with XTTS sampling and one beam it has no useful
termination effect here.

No profile passed Short-DE 3/3, so no new Long-DE or Dialogue-DE sample was
generated for a decoder variant. This preserves the bounded gate: a failing
short profile does not earn expensive quality controls.

## Guard design and proof

The second spike simulates PCM becoming available every 320 ms. It does not
allow only German words. Instead it:

1. incrementally transcribes available PCM with local Faster-Whisper
   `small/int8`;
2. fuzzily aligns the transcript prefix to the complete known input text,
   naturally permitting names, rooms, devices and mixed-language terms;
3. after complete-content alignment, looks for 300 ms below -40 dBFS and keeps
   200 ms of natural trailing silence;
4. uses `max(3.0 s, 1.5 s + 0.09 s × input characters)` only as a generous
   fallback cap.

| Control | Original | Guarded | Probe after guard | Assessment |
| --- | ---: | ---: | --- | --- |
| Baseline short run 1 | 6.592 s | 1.240 s | `Ich bin Velora.` | tail removed |
| Baseline short run 2 | 4.875 s | 1.360 s | `Ich bin Veloura.` | tail removed; name probe variant remains |
| Baseline short run 3 | 8.960 s | 1.300 s | `Ich bin Velora.` | tail removed |
| Conservative short run 1 | 2.091 s | 1.240 s | `Ich bin Velora.` | `Und?` removed |
| Conservative short run 2 | 8.960 s | 1.520 s | `Ich bin Velora.` | tail removed |
| Conservative short run 3 | 2.272 s | 1.280 s | `Ich bin Velora.` | `Bernden` removed |
| Existing Long DE | 9.568 s | 9.568 s | expected text | unchanged |
| Existing Dialogue DE | 12.352 s | 12.352 s | expected text | unchanged |

This 6/6 positive and 2/2 negative-control result establishes feasibility only.
The runner performs an offline simulation and does not yet measure incremental
ASR compute latency, cancel the live XTTS generator, prove that no already
queued PCM escapes, or cover the full DE/EN/domain/punctuation corpus. The
duration fallback alone is insufficient because it would retain roughly two
seconds of pseudo-speech for the short input. Alignment plus VAD is the part
that makes the guard selective.

## Decision and next gate

Do not select a decoding variant, implement a provider adapter or connect Core.
XTTS remains a candidate because the guard result is technically credible.
Before another go/no-go decision, a separate isolated live-generator guard
spike must measure ASR overhead and cancellation, run all canonical phrases and
adversarial pauses, verify that Long/Dialogue/Number/DE/EN outputs are never
cut, and repeat the short failure enough times to establish recall.

Evidence:

- `.run/xtts_short_de_decoding_spike.py`
- `.run/xtts_streaming_output_guard_spike.py`
- private unguarded and guarded WAVs, `metrics.json`, `tail-analysis.json` and
  transcripts under `E:/Kyrion/Data/voice-training/xtts-v2-short-de-review/`
