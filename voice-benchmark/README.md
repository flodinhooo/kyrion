# Velora F TTS benchmark

This directory contains the 2026-08-09 listening and runtime comparison for
Velora's immutable F voice profile.

- `raw/` contains the selected warm-run WAV and complete JSON metrics emitted
  by each provider-specific environment.
- `comparison/` contains named, mono 24 kHz PCM16 files normalised to -20 LUFS
  with a -2 dB true-peak target.
- `blind/` contains the same normalised files in deterministic shuffled order.
  Listen before opening `blind/mapping.json`.

All providers used the same text and canonical reference WAV. Provider-specific
sampling controls cannot be made numerically equivalent. Qwen used the sampling
profile recorded in `services/ai/voice-profiles/velora-f/manifest.json`.
Chatterbox used its existing fallback settings (`cfg_weight=0.5`,
`temperature=0.65`, `repetition_penalty=2.0`).

The Qwen JSON `generationSeconds` values measure the complete public
`generate_voice_clone()` call. They are not measured streaming time to first
audio. See the status report for interpretation and reproduction commands.
