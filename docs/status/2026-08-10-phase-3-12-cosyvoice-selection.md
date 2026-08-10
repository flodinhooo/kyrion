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

## Isolated proof result

The official revision `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc` and its
Matcha-TTS submodule were installed in the training WSL distribution. The
repository licence SHA-256 is
`c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`.
The official inference environment required Python 3.10 and pinned Setuptools
80.9.0 for the legacy Whisper build. DeepSpeed was removed because its import
requires a separate CUDA toolkit although ordinary inference does not use it.
PyTorch 2.3.1 CUDA 12.1 then imported CosyVoice successfully on the RTX 2070.

The 9.1 GiB official model snapshot loaded in 58.628 seconds. Immutable Velora
conditioning took 5.201 seconds and was cached before warm measurement. Peak
allocated model/inference VRAM was 5,006.7 MiB.

| Phrase | First PCM range | Total range | Audio range | Chunks |
| --- | ---: | ---: | ---: | ---: |
| German domain terms | 4.221–4.473 s | 4.252–5.968 s | 3.92–4.64 s | 1–2 |
| English domain terms | 4.785–5.399 s | 4.817–5.434 s | 4.92–5.76 s | 1 |

Five of six warm runs yielded the complete phrase as their first and only
chunk. The remaining German run first yielded 3.52 seconds of its 4.36-second
output after 4.271 seconds. This is technically a streaming API, but not useful
incremental playback on this hardware. Warm total RTF was roughly 0.94–1.52.

## Decision

CosyVoice 3 is **NO-GO for integration** at the cheap proof gate. It misses the
2.0-second first-PCM hard limit by more than twofold and does not expose useful
short-phrase chunks. Do not run the expensive stability/listening matrix,
optimize TensorRT/vLLM, add an adapter or connect Core. Preserve the evidence
and select no replacement until a new official runtime has credible RTX 2070
faster-than-playback evidence.

Evidence remains outside Git under `/training/cosyvoice-velora-proof/`, with
the reproducible runners `.run/cosyvoice_import_probe.py`,
`.run/download_cosyvoice_model.py` and `.run/cosyvoice_velora_proof.py`.
