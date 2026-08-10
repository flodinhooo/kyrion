# Phase 3.13 Chatterbox batch-fallback check — 2026-08-10

## Outcome

The retained Chatterbox multilingual runtime remains operational as an
isolated local batch fallback using the immutable `velora-f` reference. This
check does not make it a streaming provider, connect it to the Phase 3 PCM
downlink or change Core.

The runtime loaded and warmed successfully on the RTX 2070, reported one
`velora` voice and rejected an unknown voice with HTTP 400. A silent German
smoke request completed in 3.624 seconds and returned a valid 157,484-byte WAV:

- RIFF/WAVE container;
- mono PCM16;
- 24 kHz;
- 78,720 frames / 3.280 seconds of audio.

The output and runtime logs remain private under
`E:/Kyrion/Data/voice-training/`. No audio was played. Warm runtime GPU use was
approximately 5,451 MiB and returned to the desktop baseline after shutdown.

## Configuration debt

The standalone fallback API is healthy, but the AI service still names its
generic local HTTP batch client and settings after Qwen (`tts_provider=qwen`,
`KYRION_QWEN_TTS_URL`). No local `.env` currently selects either endpoint.
Silently pointing the Qwen-named setting at Chatterbox would preserve function
but misrepresent provider ownership. This check documents the mismatch rather
than changing production configuration during a fallback verification.

The next safe slice is to make the existing batch HTTP client provider-neutral
while retaining explicit endpoint selection and Piper behaviour. It must not
add streaming, automatic fallback or Core routing.

## Evidence

- `services/ai/runtime/chatterbox_tts_server.py`
- private `chatterbox-fallback-smoke.wav`
- private `chatterbox-fallback.stdout.log` and `.stderr.log`
