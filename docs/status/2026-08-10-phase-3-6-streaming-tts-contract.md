# Phase 3.6 provider-neutral streaming TTS contract — 2026-08-10

## Scope

This slice defines and validates the AI-side streaming-TTS boundary without
adding an HTTP route, Core integration or concrete Qwen/Chatterbox/Piper
adapter.

## Contract

Every provider declares machine-readable capabilities for incremental output,
cancellation, voice cloning, PCM format, sample rate, channel count, minimum
text granularity, text limit and maximum chunk duration. The first accepted
transport format is signed 16-bit little-endian mono PCM at an explicitly
declared supported rate.

One request is scoped to a UUID turn, locale, provider-independent voice
profile, phrase index and final-phrase flag. The upstream boundary policy may
therefore submit phrases without making the provider responsible for dialogue
or command decisions.

`ValidatedStreamingTts` treats provider output as untrusted. It emits one typed
start event, validates zero-based chunk sequence, alignment, per-chunk and
two-minute turn bounds, and emits exactly one complete or cancelled terminal.
Cancellation is shared with the provider and later audio is not forwarded.
Providers claiming more than 250 ms cancellation latency are rejected.

## Boundary

The existing batch `/v1/speech/synthesize` route and Faster-Whisper baseline are
unchanged. No provider is selected by this contract. A later isolated adapter
must pass this validator and its own latency, quality, memory and licence gates
before an HTTP streaming route or Core consumer is added.

## Evidence

- `services/ai/src/kyrion_ai/streaming_tts.py`
- `services/ai/tests/test_streaming_tts.py`
