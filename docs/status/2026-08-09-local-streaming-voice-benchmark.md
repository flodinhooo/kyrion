# Local streaming voice architecture and TTS benchmark — 2026-08-09

## Outcome

ADR 0009 establishes a fully local, provider-neutral streaming voice pipeline.
The immutable `velora-f` profile preserves the original Qwen-designed F voice
independently of Qwen or Chatterbox. Chatterbox remains the working legacy
fallback.

Qwen3-TTS-12Hz-0.6B-Base was tested as the preferred low-memory candidate. It
cannot safely replace the fallback on the current RTX 2070:

- FP16 sampling fails with NaN/Inf logits and a CUDA device assertion on the
  Turing GPU. Deterministic FP16 failed to terminate normally. This matches an
  upstream Turing/FP16 report in the
  [official Qwen repository](https://github.com/QwenLM/Qwen3-TTS/issues/43).
- FP32 works and preserves the voice-cloning path, but complete-audio latency
  remains high and simultaneous residency with Gemma leaves only 796 MiB at
  the measured TTS peak.
- The public `qwen-tts==0.1.1` API does not emit incremental audio. A separate
  internal-streaming spike is required before making a final Qwen decision.

The correct decision gate is therefore: keep Chatterbox operational, obtain the
owner's blind quality judgement, and pursue Qwen 0.6B only through a bounded
internal-streaming spike. Do not integrate it into the dialogue path yet.

## Canonical inputs

Voice profile: `services/ai/voice-profiles/velora-f/manifest.json`

Reference SHA-256:
`d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09`

Texts:

| ID | Text |
| --- | --- |
| short | Ich bin Velora. |
| medium | Ich bin Velora und begleite dich durch deinen Alltag. |
| long | Natürlich, Flo. Ich helfe dir dabei, den Überblick zu behalten und die nächsten Schritte in Ruhe zu planen. Sag mir einfach, womit wir beginnen sollen. |

Each runtime was loaded once and conditioned once. The first sample for every
text length is recorded separately, followed by three warm runs. Only the short
first run immediately follows model loading and conditioning; later first runs
may benefit from already initialised CUDA kernels. Raw per-run measurements are
stored beside the generated audio under `voice-benchmark/raw`.

## Runtime comparison

The times below are mean complete-audio times across warm runs 1–3. They are
not true streaming TTFA.

| Runtime | Precision | Short | Medium | Long | Warm RTF short / medium / long |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen 1.7B F | FP16 SDPA | 4.215 s | 9.420 s | 23.022 s | 2.874 / 2.820 / 2.672 |
| Qwen 0.6B F | FP32 SDPA | 3.413 s | 8.399 s | 19.216 s | 2.479 / 2.333 / 2.295 |
| Chatterbox F | provider runtime | 3.652 s | 4.203 s | 9.387 s | 1.234 / 1.157 / 1.073 |

Qwen 0.6B's best warm short result was 2.471 seconds. Its FP32 speedup over
Qwen 1.7B is real but modest, and Chatterbox remains much faster for medium and
long complete responses.

## Load, conditioning and memory

| Runtime | Disk size | Model load | Conditioning | Permanent allocated VRAM | Peak allocated VRAM | Process RAM peak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen 1.7B F | 4.3 GB | 33.324 s | 1.970 s | 4,050 MiB | 4,623 MiB | 4,667 MiB |
| Qwen 0.6B F | 2.4 GB | 2.241 s | 2.153 s | 4,213 MiB | 4,993 MiB | 2,726 MiB |
| Chatterbox F | 3.0 GB cache | 49.949 s | 7.069 s | 3,357 MiB | 3,619 MiB | 5,042 MiB |

Load measurements are affected by the WSL and OS file cache and are not used
as steady-state latency. Conditioning remains cached for every warm run.
Qwen 0.6B allocates more VRAM than 1.7B here because FP32 is required on this
GPU while the 1.7B runtime works in FP16.

Qwen audio decoding was a small fraction of total time. The 0.6B warm runs
spent roughly 0.24–0.52 seconds decoding; almost all remaining latency was
autoregressive codec generation. WAV writing is outside the measured generate
call and negligible compared with model inference.

## Simultaneous Gemma and Qwen 0.6B residency

Faster-Whisper remains CPU `int8` and therefore contributes no material GPU
allocation. The parallel probe loaded Qwen 0.6B FP32 and cached F conditioning,
then loaded and ran Gemma3 1B through Ollama without swapping either model per
turn.

| State | Total GPU memory used |
| --- | ---: |
| Desktop/WSL baseline | 1,296 MiB |
| Qwen 0.6B warm | 6,167 MiB |
| Qwen + Gemma warm / Gemma peak | 7,127 MiB |
| Qwen TTS peak with Gemma resident | 7,395 MiB |
| Reported physical capacity | 8,191 MiB |
| Remaining at measured TTS peak | 796 MiB |

The combined configuration completed without OOM, but 796 MiB is not a safe
production margin. The medium TTS probe took 9.027 seconds while Gemma was
resident, compared with an isolated 8.399-second warm mean. Other desktop CUDA
use, longer generations, allocator fragmentation or future runtime changes can
exhaust the remaining memory.

## Voice cloning and licences

| Runtime | Voice clone | Licence | Streaming potential | Maintenance risk |
| --- | --- | --- | --- | --- |
| Qwen 1.7B | Yes, exact cached F prompt | Apache-2.0 | Model supports it; public Python API does not emit chunks | High for a custom streaming fork |
| Qwen 0.6B | Yes, exact cached F prompt | Apache-2.0 | Same 12 Hz architecture; best candidate for a spike | High on Turing due FP16 failure and internal patching |
| Chatterbox | Yes, F reference conditioning | MIT | No native incremental output in the current path | Low as retained batch fallback |

The official Qwen model card lists both 0.6B and 1.7B Base as voice-cloning,
German and streaming-capable models and releases them under Apache 2.0:
[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) and
[Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base).

## Public API versus internal streaming

### Current complete-audio path

`generate_voice_clone()` calls the full talker generation first. The talker
collects every generated step from `talker_result.hidden_states`, stacks all 16
codec groups, trims at EOS and returns a complete code tensor. Only then does
the inference wrapper append reference codes, call the speech tokenizer decode
and return a complete NumPy waveform.

`non_streaming_mode=False` changes how text and codec embeddings are aligned;
the official docstring explicitly says it simulates streaming text input and
does not enable true streaming input or generation.

### Available codec information

Each autoregressive talker step creates the primary codec token and invokes the
code predictor for the remaining 15 groups. A complete 16-code frame therefore
exists inside `Qwen3TTSTalkerForConditionalGeneration.forward()` before the next
talker step. The public Hugging Face streamer sees only the primary generation
sequence; it does not expose the assembled 16-code frame used by the audio
decoder.

At 12.5 codec frames per second and 1,920 output samples per frame, one frame
represents 80 ms of 24 kHz audio. In principle, a decoder could start after a
small number of complete frames rather than waiting for EOS.

### Decoder behaviour

The tokenizer's `chunked_decode()` is an offline memory-bounding helper, not a
streaming iterator. Its defaults process 300 code frames at a time and prepend
25 frames of left context. It recomputes the decoder for every block, discards
the waveform corresponding to the left context and concatenates the remainder.
It carries no explicit KV, convolution or resampler state between calls.

The decoder uses causal convolution blocks, but also runs a pre-transformer and
several upsampling stages. Product-grade incremental use must verify that
re-decoding overlapping context is sample-continuous, determine a smaller safe
frame count, trim the cloned reference prefix exactly and avoid clicks or
prosody changes at boundaries. Cancellation must also stop the talker loop and
release queued decoder work.

## Streaming effort classification

Overall classification: **C — deep intervention in model/generation code** for
a product-quality adapter.

A proof-of-concept could look like a small maintained fork (B): add a callback
where each 16-code frame is assembled, queue groups, repeatedly decode the
accumulated frames with left overlap and emit only new PCM. That is not yet a
safe provider implementation because it changes internal generation behaviour
and relies on undocumented hidden-state structure.

Required tests include:

- exact equivalence or bounded difference against full decode;
- overlap sizes across short and long German speech;
- click/discontinuity detection and listening tests;
- reference-prefix trimming and speaker similarity;
- deterministic cancellation at every generation stage;
- bounded GPU memory for long turns;
- compatibility checks for every Qwen upgrade;
- FP32 behaviour and NaN detection on Turing.

Based on measured FP32 throughput, an honest first-chunk estimate is 1.5–3.0
seconds after TTS receives usable text, depending on prefill, chosen frame
window and overlap. This is an engineering estimate, not a benchmark result.
Qwen's published 97 ms architectural result must not be applied to this RTX
2070/PyTorch runtime without measurement.

## Listening test

Named normalised samples are under `voice-benchmark/comparison/{short,medium,long}`.
The blind files are under `voice-benchmark/blind`. All comparison files are
mono 24 kHz PCM16 and normalised with FFmpeg loudness filtering. Provider names
are not spoken in the samples. The owner decides subjective quality before the
runtime gate is closed.

## Reproduction

The benchmark verifies the canonical reference hash before loading a provider.
Run providers in isolation so their allocators do not affect each other:

```powershell
ollama stop gemma3:1b

wsl.exe -d Kyrion-Voice-Training -- /training/qwen3-tts-venv/bin/python `
  /mnt/e/dev/Kyrion/kyrion/.run/benchmark_velora_tts.py `
  --provider qwen `
  --model /training/models/qwen3-tts/voice-clone-base-0.6b `
  --label qwen-0.6b-f `
  --dtype float32

wsl.exe -d Kyrion-Voice-Training -- /training/qwen3-tts-venv/bin/python `
  /mnt/e/dev/Kyrion/kyrion/.run/benchmark_velora_tts.py `
  --provider qwen `
  --model /training/models/qwen3-tts/voice-clone-base `
  --label qwen-1.7b-f `
  --dtype float16

wsl.exe -d Kyrion-Voice-Training -- /training/chatterbox-venv/bin/python `
  /mnt/e/dev/Kyrion/kyrion/.run/benchmark_velora_tts.py `
  --provider chatterbox `
  --label chatterbox-f

wsl.exe -d Kyrion-Voice-Training -- python3 `
  /mnt/e/dev/Kyrion/kyrion/.run/prepare_voice_benchmark.py `
  --root /mnt/e/dev/Kyrion/kyrion/voice-benchmark
```

Run `.run/probe_qwen_06_gemma_vram.py` only after isolated measurements. It
loads Qwen FP32, starts Gemma through the Windows Ollama runtime and samples
total GPU usage. Close unrelated GPU-heavy applications before comparing its
numbers across sessions.

## Decision and next gate

Recommendation: **continue Qwen 0.6B only through a separate internal-streaming
spike**. Do not select it as the default provider yet.

Reasons:

- complete-audio performance misses the target;
- FP16 is unstable on the RTX 2070 and FP32 leaves little combined VRAM margin;
- the public API cannot provide the required chunks;
- the voice may nevertheless justify a bounded spike if the blind test confirms
  that 0.6B retains F's quality.

If the owner accepts the 0.6B voice, the next technical step before Phase 3 is a
throwaway Qwen streaming spike: expose complete 16-code frames through a
callback in a pinned Qwen fork, decode 10–25 frame windows with measured overlap
and write timestamped PCM chunks to a local sink. It must prove first playable
PCM, continuity, cancellation and VRAM behaviour without touching Core or the
Pi. Only a passing spike permits Phase 3 continuous Pi-to-Core transport.
