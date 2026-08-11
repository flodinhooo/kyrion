# Short-TTS provider benchmark — 2026-08-11

## Current decision

There is currently **no accepted dynamic Short-TTS provider** for Kyrion/Velora.
No candidate is integrated, no provider or fallback routing is changed, and Core,
Satellite and the Fixed/Template/Dynamic architecture remain untouched.

The owner listened to all Stage-1 Piper and Chatterbox WAVs and rejected both:

- **Piper: C / eliminated.** Termination and latency are strong, but quality and
  voice identity are not remotely adequate for Velora.
- **Chatterbox: C / eliminated.** Quality and voice identity are inadequate, and
  its measured Short latency is also unacceptable.

Neither candidate may enter Stage 2. Qwen and CosyVoice remain C based on the
already documented measurements and were not repeated. XTTS v2 remains the
experimental/opt-in quality reference for normal and longer answers; its Short
EOS, VAD, guard and punctuation optimisation lanes stay closed.

## Preserved first-discovery evidence

The owner decisions are recorded both in each provider's `results.json` and in a
separate `stage-1-manual-review.json`. The fourteen original WAVs and all raw
measurements remain preserved.

| Candidate | Measured Stage-1 result | Owner review | Decision |
| --- | --- | --- | --- |
| Piper 1.6.0, `de_DE-kerstin-low` | 0.028–0.077 s warm completion, RTF 0.029–0.040; no Velora cloning | Unacceptable quality and voice identity | C |
| Chatterbox Multilingual 0.1.7 | 2.044–4.686 s batch completion, RTF 1.172–1.603, about 3.5 GiB peak VRAM | Unacceptable quality/identity and Short latency | C |
| Qwen3-TTS 0.6B/1.7B | Prior work retained; strong identity, but latency/resource/custom-runtime constraints | Previously closed | C |
| Fun-CosyVoice3 0.5B | Prior proof retained; 4.2–5.4 s first PCM and usually one complete chunk | Previously closed | C |

Offline Faster-Whisper results remain hints only. ASR was not a runtime guard,
was not used to override owner listening, and is not part of any proposed Short
path.

## Second candidate discovery

Primary project repositories and official model cards were checked before any
download. The shortlist was intentionally limited; popularity alone was not a
selection criterion.

### Selected for an isolated Stage-1 smoke test

#### MOSS-TTS-Nano 100M ONNX

MOSS-TTS-Nano was the only new candidate selected for an immediate benchmark.
The official project describes a 100M CPU-first, streaming, multilingual model
with zero-shot voice cloning and lists German and English among 20 languages.
The repository and official model metadata identify Apache-2.0 licensing. The
ONNX runtime accepts direct reference audio and a seed.

Risks identified before the test:

- official issues include reports of repetition on short ONNX text and swallowed
  text, so Short reliability requires listening rather than assumption;
- the current official ONNX implementation imports PyTorch and Torchaudio despite
  its CPU/ONNX positioning, increasing installation size and maintenance burden;
- `realtime-streaming-decode` controls internal codec decoding, but the official
  Python API returns the waveform only after synthesis. It does not expose a
  playable chunk stream, so TTFA is not measurable through this path.

Official sources:

- <https://github.com/OpenMOSS/MOSS-TTS-Nano>
- <https://github.com/OpenMOSS/MOSS-TTS>
- <https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M>
- <https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX>
- <https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX>

### Research candidate, not downloaded

#### Zonos v0.1

Zonos remains a B-level research candidate because the official project supports
German and English, zero-shot voice cloning and local execution under Apache-2.0.
It was not downloaded: the official model card recommends Linux with a recent
NVIDIA 3000-series-or-newer GPU and at least 6 GB VRAM. The available RTX 2070
is outside that stated support target, while the roughly 1.6B-parameter model is
unlikely to meet this lane's sub-second objective without contrary evidence.

Official sources:

- <https://github.com/Zyphra/Zonos>
- <https://huggingface.co/Zyphra/Zonos-v0.1-transformer>

### Rejected before download

| Candidate | Verified reason not to benchmark now |
| --- | --- |
| F5-TTS | Code is MIT, but the official pretrained weights and the officially listed German fine-tune are CC-BY-NC/CC-BY-NC-4.0. This is not a clean long-term redistribution basis for Kyrion. |
| Fish Speech / S2 | German, cloning and streaming are documented, but self-hosting is governed by the Fish Audio Research License and separate commercial terms. |
| Kokoro | No current primary-source evidence established the required combination of German support and Velora-compatible voice cloning/conditioning. |
| OpenVoice V2 | MIT and cross-lingual cloning are attractive, but the official V2 native-language list does not include German. |
| NeuTTS Nano German | German cloning and CPU operation are documented, but the German model uses the NeuTTS Open License 1.0 rather than the Apache licence of the smaller Air line. |

Official sources used for these gates:

- <https://github.com/SWivid/F5-TTS>
- <https://github.com/SWivid/F5-TTS/blob/main/src/f5_tts/infer/SHARED.md>
- <https://github.com/fishaudio/fish-speech>
- <https://github.com/myshell-ai/OpenVoice>
- <https://github.com/neuphonic/neutts>

## MOSS-TTS-Nano isolated Stage 1

The official repository was installed only in the `Kyrion-Voice-Training` WSL
environment at revision
`cc7bdf19c7639c0870dab22045a33b442760f6be`. Official TTS and codec ONNX assets
were downloaded into that isolated checkout. No existing engine environment or
production dependency was modified.

Configuration:

- CPU ONNX execution, four threads;
- direct immutable Velora-F reference WAV;
- fixed sampling with recorded seeds;
- official defaults otherwise, including text/audio sampling values;
- one persistent process for fair warm measurements;
- seven DE Stage-1 WAVs from the existing shared corpus;
- no ASR classification.

Measurements:

- model load: 8.008 s;
- first synthesis/reference encoding: 8.261 s for 2.16 s audio;
- subsequent warm synthesis: 1.885–2.478 s, mean 2.211 s;
- subsequent warm RTF: 0.955–1.571, mean 1.246;
- process peak resident memory: about 3.55 GiB;
- output: stereo PCM16, 48 kHz;
- exposed TTFA: unavailable; the tested official API returns only complete WAV;
- all content, termination, pronunciation, naturalness and identity labels:
  `pending_manual_review`.

MOSS is therefore **B / manual gate pending**, not an accepted provider. Stage 2
is prohibited until the owner accepts all seven Stage-1 samples. Even with an
audio-quality pass, its current API and warm latency would still need a separate
evidence-based review before it could qualify for the sub-second Short target.

## Reproducibility and artifacts

The shared corpus is `.run/short_tts_corpus.json`. The isolated MOSS runner is
`.run/short_tts_moss_nano_stage1.py`; it records engine revision, model, codec,
configuration, seeds, inputs, timings, RTF, WAV format/hash, runtime context and
manual-review placeholders.

Private, manually playable artifacts are stored under:

```text
E:/Kyrion/Data/voice-training/short-tts-provider-benchmark/
  piper/stage-1/
  chatterbox/stage-1/
  moss-tts-nano/stage-1/
    de.identity--seed-72001.wav
    de.identity--seed-72002.wav
    de.identity--seed-72003.wav
    de.acknowledge--seed-72001.wav
    de.reject--seed-72001.wav
    de.greeting--seed-72001.wav
    de.domain--seed-72001.wav
    results.json
```

## Decision table

| Candidate | Short reliability | TTFA | RTF | DE | EN | Voice identity | Resources | Licence | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Piper Kerstin low | Owner rejected | 0.028–0.077 s warm | 0.029–0.040 | Rejected quality | Installed model unavailable | Rejected | CPU, low RAM | Runtime GPL; weight redistribution still open | C |
| Chatterbox Multilingual | Owner rejected | 2.044–4.686 s batch | 1.172–1.603 | Rejected quality | Supported, not advanced | Rejected | ~3.5 GiB VRAM | MIT recorded | C |
| Qwen 0.6B/1.7B | Prior no-go retained | ~2.3 s best accepted 1.7B stream | Slower than playback in relevant runs | Good prior samples | Good prior samples | Strong | High VRAM/custom path | Apache-2.0 recorded | C |
| CosyVoice3 0.5B | Prior no-go retained | 4.2–5.4 s | ~0.94–1.52 | Generated | Generated | Not promoted | ~5.0 GiB VRAM | Artifact review incomplete | C |
| MOSS-TTS-Nano ONNX | `pending_manual_review` | Not exposed by official tested API | 0.955–1.571 warm; mean 1.246 | Pending listening | Claimed; not Stage 2 tested | Pending listening | CPU; ~3.55 GiB RSS | Apache-2.0 recorded | B |
| Zonos v0.1 | Not tested | Not tested | Not tested | Officially supported | Officially supported | Clone-capable | Official target is newer GPU, ≥6 GB VRAM | Apache-2.0 | B research only |

**Accepted Short-TTS provider: none.** No winner is inferred from technical WAV
generation, and no Stage-2 work has started.
