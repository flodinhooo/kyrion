# Phase 3.8 isolated Qwen runtime gate — 2026-08-10

## Scope

This slice adds the Phase 3.6 capability and NDJSON interfaces to a separate,
isolated Qwen3-TTS 1.7B runtime and exercises them through the Phase 3.7
adapter. It does not register Qwen as a selectable provider, change Core or
connect the runtime to the Voice Satellite.

The runtime preserves the previously accepted spike configuration: warm FP16
SDPA on the RTX 2070, immutable `velora-f` conditioning, ten initial codec
frames, 20-frame stride, 50-frame decoder context, no crossfade and 24 kHz
mono PCM16 output. Its bounded four-event queue applies backpressure and its
turn-scoped cancellation endpoint interrupts generation.

## Measured adapter result

Three warm phrases were transported through the real adapter. The private WAV
files and JSON report remain outside Git under
`E:/Kyrion/Data/voice-training/phase38-qwen-adapter/`.

| Phrase | First audio | Total generation | Audio | Chunks | Longest update gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| DE domain terms | 2.438 s | 10.577 s | 3.60 s | 3 | 4.519 s |
| EN domain terms | 2.734 s | 13.473 s | 4.56 s | 4 | 4.582 s |
| Longer DE response | 2.458 s | 16.415 s | 6.08 s | 5 | 4.304 s |

Active cancellation after the first audio event produced a typed cancelled
terminal in 208.3 ms, within the declared 250 ms bound. Capability discovery,
format and sequence validation, explicit completion and cancellation all pass.

The owner judged the short German and English samples good. The English
pronunciation of `Velora` could be polished but was understandable and is not
an acceptance failure. The longer German sample had a small audible jerk
between `Guten` and `Morgen`, consistent with a codec chunk boundary.

## Decision

Phase 3.8 is complete, but the runtime gate is **NO-GO for Core integration**.
Its 2.4–2.7 second first audio latency is above an interactive target and its
4.3–4.6 second update gaps cannot sustain continuous playback. The isolated
contract implementation is valid evidence, not a production provider.

Do not optimize Qwen further in this phase, expose these endpoints through the
AI application, connect them to Core or replace the operational Chatterbox
fallback. A future TTS candidate must produce continuously faster than playback
while preserving the accepted Velora voice quality and bounded cancellation.

## Evidence

- `services/ai/runtime/qwen_streaming_tts_server.py`
- `services/ai/src/kyrion_ai/providers/qwen_streaming_tts.py`
- `services/ai/tests/test_qwen_streaming_tts.py`
- `.run/phase38_qwen_adapter_acceptance.py`
- private `acceptance.json` and three listening WAV files
