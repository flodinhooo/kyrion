# Phase 3.9 provider-neutral TTS phrase boundary — 2026-08-10

## Outcome

The AI boundary now has an isolated, provider-neutral policy that converts an
incremental LLM text stream into bounded TTS phrases. It is not connected to
the production chat route, Core, a speech provider or Satellite playback.

The policy emits complete sentences as soon as terminal punctuation arrives,
flushes an unpunctuated final tail, preserves domain terms without rewriting,
avoids common German and English abbreviation boundaries, and splits text at a
whitespace boundary before 180 characters. Cancellation discards buffered and
future text.

Short fragments below 12 characters are deliberately buffered unless the text
stream ends. This avoids sending uneconomical one-word fragments to a provider
while retaining early sentence delivery. A phrase emitted before stream
completion cannot truthfully claim to be the final phrase; end-of-turn remains
an explicit downstream lifecycle concern.

## Verification

- AI Ruff: pass.
- AI tests: 69 passed.
- Tests cover incremental sentence emission, `Velora` / `Gamingraum` /
  `desk lamp`, abbreviations, the hard length bound and cancellation.

## Boundary and next slice

This slice does not revive the rejected Qwen integration or change the legacy
Chatterbox fallback. The next safe slice may compose a mock LLM token stream,
this phrase policy and a synthetic streaming-TTS provider to verify ordering,
phrase indices, terminal state and one cancellation signal end to end without
audio hardware or provider selection.

## Evidence

- `services/ai/src/kyrion_ai/tts_phrase_boundary.py`
- `services/ai/tests/test_tts_phrase_boundary.py`
