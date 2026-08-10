# Phase 3.14 provider-neutral batch-TTS client — 2026-08-10

## Outcome

The AI service's existing local HTTP batch-TTS client is no longer named after
Qwen. `http_batch` is the explicit default and uses `KYRION_HTTP_TTS_URL`,
whose local-development default is the retained Chatterbox runtime on port
8020. Piper remains a separate explicit provider.

This is not automatic fallback: one configured provider and endpoint are used,
and failures remain typed as `SpeechUnavailableError`. Existing deployments
that explicitly select `qwen` retain the legacy `KYRION_QWEN_TTS_URL` endpoint
as a compatibility alias. No Qwen runtime is selected by the new default.

The provider-neutral client was exercised against the real isolated
Chatterbox runtime. It discovered one default `velora` voice and synthesized a
valid 3.44-second, mono 24 kHz PCM16 WAV in 4.348 seconds.

## Verification

- AI Ruff: pass.
- AI tests: 72 passed.
- Tests cover unreachable HTTP batch runtime, provider-neutral synthesis,
  explicit legacy Qwen endpoint selection and unchanged Piper validation.
- Real local provider-neutral client to Chatterbox: pass.

## Boundary

This slice changes no Core route, streaming contract, Satellite transport or
provider selection at runtime outside the AI service default configuration.
Chatterbox remains batch-only and Qwen/CosyVoice remain streaming no-go
candidates.

## Evidence

- `services/ai/src/kyrion_ai/config.py`
- `services/ai/src/kyrion_ai/speech.py`
- `services/ai/.env.example`
- `services/ai/tests/test_config.py`
- `services/ai/tests/test_speech.py`
- `.run/phase314_http_batch_acceptance.py`
