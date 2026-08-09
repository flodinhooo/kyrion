# Qwen 1.7B internal streaming spike — 2026-08-10

## Scope and outcome

This spike tests whether the preferred Qwen3-TTS-12Hz-1.7B Velora F voice can
produce early local PCM on the RTX 2070. It does not implement or modify Core,
the Dialogue Controller, Voice Satellite transport, Raspberry Pi playback,
streaming STT or the configured Chatterbox fallback.

The spike is technically successful at a five-frame window: after an explicit
model, talker and decoder warm-up, first playable PCM arrived in 1.09–1.48
seconds across the nine measured short, medium and long runs. Ten-frame output
arrived in 1.99–2.58 seconds. Larger windows missed the latency gate.

Final classification is **PASS with an accepted quality/latency compromise**.
After the initial matrix and a focused boundary-optimisation follow-up, the
owner accepted a ten-frame first decode followed by 20-frame strides as nearly
full-decode quality. Cancellation, sample counts and memory are stable. The
non-crossfaded candidate was technically stronger than the crossfaded variant.

## Implementation

`.run/qwen_17_streaming_spike.py` loads the existing 1.7B Base model once with
CUDA FP16 and SDPA, creates the immutable F clone prompt once and keeps both
warm. It installs an in-memory wrapper around the loaded talker's `forward()`;
the installed Qwen package is not modified.

Every autoregressive talker step exposes the primary code and the 15 sub-talker
codes through `Qwen3TTSTalkerOutputWithPast.hidden_states`. The wrapper validates
and emits the complete 16-code frame to an `on_frame(index, frame)` callback
before EOS. The original full-generation path remains available for a
sample-matched control decode.

The decoder uses 25 frames of left context. The first chunk uses the final 25
reference frames plus new generated frames and removes exactly 25 × 1,920
context samples. Later chunks use up to 25 already generated frames as left
context and emit only the new `window × 1,920` samples. No network or playback
buffer is involved.

Events are timestamped from `TTS_TEXT_AVAILABLE`:

- `FIRST_CODEC_FRAME`;
- `FRAME_5_READY` through `FRAME_25_READY`;
- `FIRST_DECODE_START`;
- `FIRST_PLAYABLE_PCM`;
- subsequent `CHUNK_n` events;
- `GENERATION_COMPLETE`.

## Aggregate window results

Each value below aggregates three warm runs for each of the three texts, nine
runs per frame window. Complete-generation time varies with text length and is
therefore included mainly as a runtime-cost indicator.

| Window | First codec frame | First playable PCM | Generation complete | RTF | Peak allocated VRAM |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 frames | 0.267 s | 1.189 s | 12.393 s | 2.853 | 4,618 MiB |
| 10 frames | 0.296 s | 2.291 s | 11.885 s | 2.754 | 4,618 MiB |
| 15 frames | 0.264 s | 3.235 s | 11.773 s | 2.677 | 4,618 MiB |
| 20 frames | 0.270 s | 4.297 s | 12.550 s | 2.743 | 4,618 MiB |
| 25 frames | 0.289 s | 4.997 s | 12.207 s | 2.714 | 4,618 MiB |

The decoder work competes with autoregressive generation on the same GPU.
Smaller windows provide earlier audio but increase total decode calls and make
complete generation slower. This is acceptable for the spike because perceived
latency, not total synthesis time, is the primary gate.

## Results by text and window

| Text | Frames | First codec | First PCM | Complete | RTF | VRAM peak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Short | 5 | 0.267 s | 1.296 s | 4.007 s | 3.042 | 4,396 MiB |
| Short | 10 | 0.278 s | 2.384 s | 3.731 s | 2.864 | 4,396 MiB |
| Short | 15 | 0.265 s | 3.288 s | 3.561 s | 2.719 | 4,396 MiB |
| Short | 20 | 0.246 s | 3.696 s | 3.419 s | 2.611 | 4,396 MiB |
| Short | 25 | 0.275 s | 3.582 s | 3.497 s | 2.679 | 4,396 MiB |
| Medium | 5 | 0.268 s | 1.118 s | 9.110 s | 2.735 | 4,458 MiB |
| Medium | 10 | 0.312 s | 2.348 s | 9.262 s | 2.778 | 4,458 MiB |
| Medium | 15 | 0.251 s | 3.116 s | 8.901 s | 2.668 | 4,458 MiB |
| Medium | 20 | 0.272 s | 4.393 s | 9.016 s | 2.701 | 4,458 MiB |
| Medium | 25 | 0.290 s | 5.410 s | 8.843 s | 2.652 | 4,458 MiB |
| Long | 5 | 0.277 s | 1.154 s | 24.062 s | 2.783 | 4,618 MiB |
| Long | 10 | 0.297 s | 2.141 s | 22.661 s | 2.621 | 4,618 MiB |
| Long | 15 | 0.275 s | 3.301 s | 22.858 s | 2.645 | 4,618 MiB |
| Long | 20 | 0.291 s | 4.804 s | 25.214 s | 2.918 | 4,618 MiB |
| Long | 25 | 0.302 s | 5.999 s | 24.281 s | 2.812 | 4,618 MiB |

## Audio integrity

Every assembled streaming WAV has exactly the same number of samples as its
sample-matched full decode. The spike inserts no zero padding or artificial
pause and duplicates or drops no complete frame region. All outputs are mono
24 kHz PCM16.

Increasing the window reduces waveform deviation from full decode:

| Window | Mean aligned RMSE | Maximum raw boundary jump |
| ---: | ---: | ---: |
| 5 | 0.02400 | 0.10211 |
| 10 | 0.02067 | 0.08734 |
| 15 | 0.01200 | 0.09714 |
| 20 | 0.01033 | 0.03590 |
| 25 | 0.00967 | 0.03595 |

A raw boundary jump is not automatically a click because the control waveform
can have a natural discontinuity at the same sample. Comparison against the
sample-matched full decode found small excess jumps in most files, but the long
10-frame sample includes one conspicuous technical candidate. Clicks, timbre
change and prosody remain listening-test gates; they cannot be accepted from
numeric metrics alone. Five-frame output has the best latency but the largest
number of boundaries.

## Cancellation

Cancellation is an in-process event checked before and after every talker step
and before each chunk decode. Raising the spike's private cancellation exception
unwinds the Hugging Face generation loop and prevents further chunk writes.

| Requested after | Successful | Mean request-to-stop | Maximum request-to-stop |
| ---: | ---: | ---: | ---: |
| 500 ms | 3/3 | 140.1 ms | 225.4 ms |
| 1,000 ms | 3/3 | 38.5 ms | 83.3 ms |
| 2,000 ms | 3/3 | 63.0 ms | 125.5 ms |

Allocated memory after cancellation stayed between 4,050.189 and 4,050.193
MiB. Reserved memory stayed at 4,818 MiB. No further PCM chunks were written
after `CANCEL_REQUESTED`, and no increasing allocation was observed across the
nine cancellation runs.

## Memory stability

- Warm allocated model memory: approximately 4,050 MiB.
- Short peak: 4,396 MiB.
- Medium peak: 4,458 MiB.
- Long peak: 4,618 MiB.
- Process RAM peak: 4,657 MiB.
- Long generations remained bounded; peak growth follows the expected retained
  generation cache and returns to the stable warm allocation for later runs.

Gemma was deliberately not loaded during this spike. The previous parallel
residency benchmark already established that Qwen plus Gemma can fit with a
narrow margin; repeating it would not answer the codec-boundary quality gate.

## Listening files

Use `voice-streaming-spike-warm/listening`. Each of `short`, `medium` and `long`
contains:

- `full-decode.wav`;
- `streaming-5-frames.wav`;
- `streaming-10-frames.wav`;
- `streaming-15-frames.wav`;
- `streaming-20-frames.wav`;
- `streaming-25-frames.wav`.

The owner should compare clicks, pauses, F timbre, phrase continuity and
prosody. The technical recommendation depends especially on whether the
five-frame variant remains acceptable, because it is the only configuration
comfortably below two seconds on the current GPU.

## Gate and recommendation

The initial gate was **BORDERLINE** pending subjective listening. That gate is
now closed as **PASS with an accepted quality/latency compromise**; see the
final listening decision below.

- If five frames sound clean and retain F: continue Qwen 1.7B toward Phase 3.
- If five frames click but ten frames sound clean: Qwen remains usable, but the
  2.29-second mean TTS TTFA leaves less room for STT and dialogue latency.
- If neither five nor ten frames is acceptable: stop Qwen product integration,
  preserve it as the quality reference and evaluate another local streaming
  TTS runtime.

If the owner accepts five frames, the minimal next Phase-3 step is only a typed
continuous PCM uplink prototype from the already-woken satellite to Core. It
should carry authenticated `sessionId`, `turnId`, PCM format and monotonically
increasing sequence numbers while leaving the existing batch dialogue path in
place. No TTS downlink or barge-in should be added until that one-way transport
is measured and accepted.

## Boundary-optimisation follow-up

The owner found the short and medium five-frame samples acceptable. In the long
sample, the difference from the full decode decreased as the window grew and
became practically inaudible at 20 frames. This indicates accumulated decoder
boundary differences rather than a general failure of early five-frame audio.

An isolated follow-up tested the long text three times per strategy with the
same seeds. It changed no production component. Three mechanisms were separated:

1. increasing left decoder context from 25 to 50 frames;
2. keeping the first 5/10-frame latency but using 20-frame strides afterwards;
3. retaining 40 ms at each boundary and crossfading the old tail with the same
   interval reconstructed by the next contextual decode.

The crossfade does not insert silence and is not a jitter buffer. It reconciles
two decoder reconstructions of the same temporal samples. Exactly 40 ms of tail
must remain mutable until the next decode; the first chunk still exposes 360 ms
or 760 ms of immediately playable PCM.

| Strategy | First PCM mean | Decode calls | Aligned RMSE | Maximum boundary jump |
| --- | ---: | ---: | ---: | ---: |
| Fixed 5, context 25 | 1.248 s | 22.3 | 0.017807 | 0.102112 |
| Fixed 5, context 50 | 1.306 s | 22.3 | 0.016705 | 0.131638 |
| Start 5, then 20, context 50 | 1.139 s | 6.7 | 0.016591 | 0.131363 |
| Start 5, then 20, 40 ms crossfade | **1.064 s** | **6.7** | 0.016631 | **0.036682** |
| Fixed 10, context 25 | 2.267 s | 11.7 | 0.014607 | 0.087341 |
| Fixed 10, context 50 | 3.274 s | 11.7 | 0.013438 | 0.101074 |
| Start 10, then 20, context 50 | 2.309 s | 6.7 | 0.013340 | 0.100952 |
| Start 10, then 20, 40 ms crossfade | 2.131 s | 6.7 | 0.013385 | 0.128357 |

All variants remain sample-exact in length and peak at 4,618 MiB allocated
VRAM. More left context alone slightly reduces global RMSE but does not reduce
the worst boundary jump and produced a 5.4-second outlier in one ten-frame run.
It is therefore not a sufficient fix. Adaptive 20-frame strides reduce the
number of long-text decode boundaries by roughly 70% without delaying the first
chunk. The 40-ms crossfade is technically promising for the five-frame start,
but it did not consistently improve the ten-frame boundary metric. Subjective
listening remains the gate, especially because RMSE does not measure prosody or
timbre.

The focused recommendation is to listen to the matched files in
`voice-streaming-boundary-optimization/listening`, especially:

- `00-full-decode.wav`;
- `01-fixed-5-context-25.wav`;
- `03-start-5-then-20.wav`;
- `04-start-5-then-20-xfade-40ms.wav`;
- `05-fixed-10-context-25.wav`;
- `07-start-10-then-20.wav`;
- `08-start-10-then-20-xfade-40ms.wav`.

If the five-frame adaptive crossfade is audibly transparent, it supersedes the
original fixed-window candidate. Otherwise the adaptive strategy without
crossfade is the safer next candidate. Phase 3 remains blocked on this listening
gate and was not started.

## Final owner listening gate and decision

The owner directly compared `00`, `03`, `04`, `07` and `08`. Both ten-frame
start variants (`07` and `08`) were substantially closer to the full decode
than the five-frame variants and were judged almost indistinguishable from the
full-decode reference. The owner therefore selected a 10-frame first chunk
followed by 20-frame chunks as the preferred quality/latency compromise.

Between the two accepted-sounding ten-frame variants, the non-crossfaded `07`
is the technical winner:

| Candidate | First PCM mean | Aligned RMSE | Maximum boundary jump |
| --- | ---: | ---: | ---: |
| `07` start 10, then 20 | 2.309 s | **0.013340** | **0.100952** |
| `08` start 10, then 20 + 40 ms crossfade | 2.131 s | 0.013385 | 0.128357 |

The small apparent TTFA advantage of `08` is not caused by crossfading, which
happens after decoding, and is therefore treated as run variance. `08` has both
a slightly higher waveform error and a materially higher worst measured
boundary jump. Crossfading adds mutable-tail state without demonstrating a
robustness benefit for the selected ten-frame path. Candidate `07` is retained.

Final spike classification: **PASS with an accepted quality/latency
compromise**. Qwen 1.7B FP16, the immutable cached F conditioning, a 10-frame
first decode, 20-frame subsequent strides and 50 frames of left context are the
selected inputs for the future provider prototype. The measured 2.309-second
mean TTS TTFA misses the ideal two-second threshold but remains below the
three-second investigation ceiling, preserves F close to full-decode quality,
cancels reliably and stays within the isolated RTX 2070 memory envelope.

Phase 3 was not started. Its minimal first step is a typed, authenticated,
continuous PCM16 uplink from the already-woken Voice Satellite to a new bounded
Core ingress prototype. It should carry `sessionId`, `turnId`, sample rate,
channel count and monotonically increasing frame sequence numbers. The first
slice ends after Core receives, orders and records timing for the PCM frames;
it does not yet add streaming STT, a TTS downlink, dialogue replacement,
playback or barge-in.

## Reproduction

```powershell
ollama stop gemma3:1b

wsl.exe -d Kyrion-Voice-Training -- `
  /training/qwen3-tts-venv/bin/python `
  /mnt/e/dev/Kyrion/kyrion/.run/qwen_17_streaming_spike.py `
  --output /mnt/e/dev/Kyrion/kyrion/voice-streaming-spike-warm

services/ai/.venv/Scripts/python.exe `
  .run/prepare_qwen_streaming_spike_results.py `
  --root voice-streaming-spike-warm
```

The script verifies the canonical F SHA-256 before loading the model. Model,
conditioning, talker and codec decoder are warmed before the measured matrix.
All provider settings match the preserved Qwen F sampling profile.
