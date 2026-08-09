# Qwen Streaming Spike Closeout — 2026-08-10

## Outcome

The isolated Qwen3-TTS-12Hz-1.7B internal-streaming spike is closed with a
**PASS with an accepted quality/latency compromise**. No production voice
provider, Core contract, Dialogue Controller, Raspberry Pi audio transport or
streaming STT implementation was changed.

The immutable `velora-f` reference and cached conditioning remain the voice
source. Qwen stays FP16, SDPA and permanently warm in the tested design.
Chatterbox remains the working batch fallback.

## Accepted streaming candidate

The owner compared the full decode against fixed and adaptive 5/10-frame
outputs. Short and medium speech tolerated five-frame chunks, but differences
accumulated in the long response. The adaptive ten-frame candidates sounded
almost identical to the full decode.

Accepted spike configuration:

- first decode after 10 complete 16-code frames;
- subsequent decode stride of 20 frames;
- 50 generated frames of left decoder context where available;
- no crossfade;
- emit only the newly decoded PCM16 region;
- mono, 24 kHz output;
- cached F conditioning and warm Qwen 1.7B FP16 model.

The non-crossfaded candidate was selected over the 40-ms crossfade candidate.
It had slightly lower aligned RMSE (`0.013340` versus `0.013385`) and a lower
worst boundary jump (`0.100952` versus `0.128357`). The crossfade's apparent
TTFA difference cannot be attributed to crossfading and is treated as run
variance. It adds state without a measured robustness benefit.

Accepted candidate measurements across three warm long-text runs:

| Metric | Result |
| --- | ---: |
| First playable PCM, mean | 2.309 s |
| First playable PCM, range | 2.086–2.531 s |
| Decode calls, mean | 6.7 |
| Generation complete, mean | 26.388 s |
| Aligned RMSE | 0.013340 |
| Maximum boundary jump | 0.100952 |
| Peak allocated VRAM | 4,618 MiB |
| Output length difference | 0 samples |

The existing cancellation spike remains valid: all nine cancellation runs
stopped, mean request-to-stop latency was 39–140 ms depending on request time,
no later chunks were written and memory returned to a stable allocation.

## Runtime state at closeout

- Chatterbox health returned `ready` with one configured voice.
- `gemma3:1b` was restored warm in Ollama after the isolated work.
- All nine boundary-comparison WAV files validate as mono 24 kHz PCM16.
- The original F reference checksum remains unchanged.
- Phase 3 has not started.

## Exact continuation point

Begin Phase 3.1 as one bounded transport slice only:

```text
already-woken Voice Satellite
        |
        | continuous PCM16 frames
        | sessionId, turnId, format, sequence, timestamp
        v
authenticated bounded Core ingress
        |
        v
ordering + timing + bounded-buffer verification
```

The first acceptance test proves authenticated delivery, ordering, bounded
buffering, disconnect/cancellation handling and measured satellite-to-Core
latency. It ends before transcription. Do not add streaming STT, Qwen output
transport, Pebble playback, jitter buffering, Dialogue Controller replacement
or barge-in in this slice.

After the uplink passes, add CPU-int8 streaming STT as the next separately
measured slice. Qwen product-provider integration happens later behind the
provider abstraction; the spike script must not become production code.

## Evidence

- `docs/status/2026-08-10-qwen-17-streaming-spike.md`
- `voice-streaming-spike-warm/aggregate.json`
- `voice-streaming-boundary-optimization/aggregate.json`
- `voice-streaming-boundary-optimization/listening/`
- `.run/qwen_17_streaming_spike.py`
- `.run/qwen_17_streaming_boundary_optimization.py`
