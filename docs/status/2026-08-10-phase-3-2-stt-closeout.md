# Phase 3.2 streaming STT closeout — 2026-08-10

## Outcome

Phase 3.2 is closed without a production streaming-STT change.
Faster-Whisper `small/int8` remains Kyrion's productive bounded final-transcript
baseline. Its rolling-window variant was rejected for latency, and the faster
`base/int8` variant was rejected for German recognition quality.

Nemotron 3.5 ASR remains a documented **NO-GO** candidate. Its official CPU Q8
runtime demonstrated stable incremental partials, no hallucinations in the six
fixed non-speech clips and sub-second finals, but it only tied the baseline at
16/20 usable sentence meanings and regressed the critical `desk lamp` result.
No further Nemotron optimisation, Core integration or replacement work is
planned.

Future candidates use the weighted acceptance gate in
[`docs/voice-stt-spike-acceptance.md`](../voice-stt-spike-acceptance.md).
Domain identity and command meaning carry more weight than aggregate WER.

## Preserved production boundary

- Core and the Voice Pipeline retain their existing batch/final STT behaviour.
- Faster-Whisper `small/int8` remains the explicit local baseline.
- STT partials never authorise or execute actions.
- Nemotron artifacts and private metrics remain isolated outside the product
  runtime and Git.

## Next slice

Phase 3.3 is the provider-neutral bounded PCM downlink transport slice. It will
prove authenticated session/turn scoping, typed format and sequence metadata,
bounded buffering, cancellation, disconnect and transport timing with
synthetic PCM. It ends before Qwen provider integration, Pebble playback,
jitter buffering, Dialogue Controller replacement or barge-in.

