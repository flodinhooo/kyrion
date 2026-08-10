# Phase 3.10 synthetic streaming voice-turn composition — 2026-08-10

## Outcome

The provider-neutral AI contracts can now be composed in isolation from an
incremental text source through phrase segmentation to validated PCM events.
The composition assigns stable phrase indices, preserves each provider-local
audio sequence, totals chunks and bytes, and emits one typed turn terminal.

A single shared cancellation signal stops the active synthetic provider,
prevents later phrases from starting and produces one cancelled turn terminal.
No HTTP route, provider selection, Core change, device command or physical
playback was added.

## Verification

- AI Ruff: pass.
- AI tests: 71 passed.
- Synthetic composition tests cover two ordered phrases and mid-first-phrase
  cancellation with no second provider request.

## Decision

The internal contract chain is ready for a future accepted streaming-TTS
provider. It must not be connected to production using Qwen, whose Phase 3.8
runtime gate failed, or used to weaken Core's turn authority. Further pipeline
integration is gated on a local TTS runtime that sustains audio faster than
playback with acceptable voice quality and bounded cancellation.

## Evidence

- `services/ai/src/kyrion_ai/streaming_voice_turn.py`
- `services/ai/tests/test_streaming_voice_turn.py`
