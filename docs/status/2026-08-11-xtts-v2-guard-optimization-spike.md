# XTTS v2 guard optimisation spike — 2026-08-11

## Decision

The cheaper guard strategies materially improve latency but no measured variant
passes safety, quality and real-time gates together. XTTS v2 therefore remains
**NO-GO for integration on the current MVP runtime**. No provider or Core code
was added.

This decision supersedes only the previously open optimisation gate. It does
not claim that a future XTTS runtime exposing stable semantic progress or a
different hardware/runtime profile can never qualify.

## Compared strategies

The live matrix uses the immutable Velora-F reference, native 20-token XTTS
streaming and the original decoding parameters. Six Short-DE seeds are followed
by Medium, Long, Dialogue, Numbers DE/EN, Domain DE/EN and two adversarial
natural-pause cases per alignment strategy.

| Strategy | ASR calls, mean | Check latency | TTFA max | RTF range | Total underruns | Short tail recall | Post-decision PCM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous small/cumulative/every chunk | every yield | 1.16–1.56 s | 3.52 s | 1.61–3.25 | 13/19 runs affected | 10/10 | 0 s |
| VAD + small cumulative | 2.20 | 1.25–1.53 s median | 0.673 s | 0.692–2.158 | 25 events | 6/6 | 0 s |
| VAD + small incremental tail | 2.13 | 1.20–1.37 s median | 0.652 s | 0.771–2.097 | 26 events | 6/6 | 0 s |
| VAD + tiny incremental tail | 2.20 | 0.241–0.280 s median | 0.700 s | 0.744–2.237 | 16 events | 6/6 | 0 s |

Energy VAD is effective: ordinary chunks become playable immediately and ASR
runs only at newly observed 300 ms pauses. This restores sub-second TTFA. Tail
alignment reduces checked audio but barely changes `small/int8` latency because
fixed model work dominates. `tiny/int8` cuts check latency by roughly fivefold.

None meets continuous playback. Tiny still records one Short underrun, Long RTF
1.129 with five underruns, Dialogue RTF 1.196, and additional underruns on
Medium, Domain EN and both pause controls. The adversarial pauses are not cut,
and all retained Short outputs are clean, so the remaining failure is runtime
performance rather than tail recall.

## Lighter forced-alignment assessment

Faster-Whisper Tiny is the measured lightweight bilingual local candidate. It
does not need a language-specific word allowlist and preserves names and mixed
DE/EN terms through fuzzy known-text matching.

PyTorch's official multilingual forced-alignment option is `MMS_FA`, a
Wav2Vec2 forced-alignment bundle trained across 1,100+ languages. It is not a
credible cheaper next measurement here: it adds another large acoustic model,
requires language-specific transcript normalisation/romanisation, and the
official TorchAudio forced-alignment APIs are deprecated and removed from the
documented forward path. Tiny already reaches 0.24–0.28 seconds per check yet
cannot preserve the playback gate; a larger deprecated bundle does not justify
another download or matrix.

## XTTS-internal guard

XTTS uses audio EOS token `8193`, but `inference_stream()` exposes neither EOS
probability nor stable text-to-code progress. Extra generator kwargs cannot set
`max_new_tokens`: XTTS already supplies an internal `max_length`, and
Transformers rejects both simultaneously.

For measurement only, the spike temporarily changes the internal, non-public
`model.gpt.max_gen_mel_tokens` and restores it after every run. The generous cap
is `max(48, 14 × normalised word count)` audio codes.

| Metric | Internal cap result |
| --- | ---: |
| TTFA | 0.532–0.678 s |
| RTF | 0.619–0.745 |
| Underruns | 0/19 |
| Long/Dialogue/Numbers/Domain/Pause completeness | 9/9 probe-complete |
| Short content correctness | 7/10 |

Nine of ten Short runs terminate exactly at the 48-code ceiling rather than
EOS. Independent probes include `Ich bin Velua`, `Ey, ich bin Velora`, only
`Äh, ja. Mann!`, and an extra `Ja, na`. A code-length cap bounds cost but cannot
prove semantic completion and can preserve bad content or hard-cut valid
prosody. Its only usable control is internal and unstable. It is therefore not
a safe integration mechanism despite excellent performance.

## Evidence

- `.run/xtts_live_guard_optimization_spike.py`
- `.run/xtts_internal_length_guard_spike.py`
- VAD/alignment WAVs and raw events:
  `E:/Kyrion/Data/voice-training/xtts-v2-live-guard-optimization-review/`
- internal-cap WAVs and probes:
  `E:/Kyrion/Data/voice-training/xtts-v2-internal-length-guard-review/`

No further combination is authorised by this result. Combining a fragile
internal cap with Tiny alignment would add both mechanisms while retaining the
observed incorrect/missing Short content; it cannot turn a failed source sample
into the requested sentence.
