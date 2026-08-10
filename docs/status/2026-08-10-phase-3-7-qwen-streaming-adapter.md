# Phase 3.7 isolated Qwen streaming-TTS adapter — 2026-08-10

## Scope

This slice maps a hypothetical capability-reporting Qwen streaming runtime into
the accepted Phase 3.6 provider-neutral contract. It does not change provider
selection, expose an AI HTTP route, start the Qwen model or connect Core.

## Adapter gate

The adapter refuses to invent capabilities from a provider name. It first reads
the runtime's machine-readable capability document. The shared validator then
rejects unsupported format, channel count, limits or cancellation slower than
250 ms.

For synthesis, the adapter sends typed turn, locale, provider-independent voice
profile and phrase metadata. It incrementally decodes bounded NDJSON PCM events,
closes on cancellation, rejects unknown/oversized/malformed events and requires
an explicit terminal event.

Mock-runtime tests prove mapping and failure behaviour. The current Qwen runtime
does not implement these endpoints, so Qwen remains unavailable through this
adapter and no integration claim is made.

## Evidence

- `services/ai/src/kyrion_ai/providers/qwen_streaming_tts.py`
- `services/ai/tests/test_qwen_streaming_tts.py`
