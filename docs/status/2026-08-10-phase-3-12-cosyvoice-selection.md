# Phase 3.12 streaming-TTS candidate selection — 2026-08-10

## Selected isolated candidate

Select only `Fun-CosyVoice3-0.5B-2512` for the next local spike. This is a
benchmark selection, not a provider or Core integration decision.

The official [CosyVoice repository](https://github.com/FunAudioLLM/CosyVoice)
states that the 0.5B model supports German and English, multilingual and
cross-lingual zero-shot voice cloning, audio-output streaming and text-input
streaming. The project includes a streaming inference mode with KV cache and
SDPA, identifies the model as 0.5B and publishes its code under Apache-2.0. The
official repository recommends this model for current inference, and the
[official model repository](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)
is available separately.

These are preconditions only. The upstream claim of latency as low as 150 ms
is not transferable to Kyrion's RTX 2070, `velora-f` reference or DE/EN texts.
VRAM use, actual licence files for every downloaded artifact and Turing support
must be recorded from the isolated installation before a full benchmark.

## Rejected alternatives for this spike

- Fish Speech S2 advertises strong streaming performance, but its weights use
  the Fish Audio Research License and commercial self-hosting has a separate
  paid policy. That adds avoidable product uncertainty at this stage.
- IndexTTS provides zero-shot cloning but does not provide equally clear
  official evidence for the required true incremental audio path.
- Qwen is frozen after the Phase 3.8 no-go and is not reconsidered.

## Spike boundary

Install CosyVoice into the isolated `Kyrion-Voice-Training` WSL distribution,
outside the product service environment. First prove model load, exact
`velora-f` reference conditioning and one DE/EN output. Only then run the full
Phase 3.11 latency, continuous-buffer, cancellation, memory, stability and
listening matrix. Do not add an AI route or adapter during the spike.
