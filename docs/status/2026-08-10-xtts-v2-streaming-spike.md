# XTTS v2 streaming TTS spike — 2026-08-10

## Scope and decision

This isolated spike evaluates Coqui XTTS v2 as a local MVP streaming-TTS
candidate on the RTX 2070. It uses the immutable `velora-f` reference and the
shared German and English acceptance texts. It does not add a provider, change
Core or the AI service, or plan an integration.

The initial result was a **NO-GO for immediate integration**, not a final model
rejection. Its native streaming generator is fast
enough with a 20-token chunk: all 24 warm turns stay faster than playback and
the simulated 320 ms playback buffer never empties. It nevertheless fails the
quality gate reproducibly: all three short German runs generate 5.29–10.63
seconds of audio for `Ich bin Velora.`, and the retained listening sample adds
several seconds of unintelligible pseudo-speech after the correct sentence.
The English domain sample pronounces `Velora` as `Villora`; the German domain
sample renders `Gamingraum` as `Gaminraum`. Process RSS also grows by 214 MiB
across the 24-turn sequence rather than demonstrating a stable plateau.

Speed alone is therefore not sufficient to justify an adapter or integration.
The operational Chatterbox batch fallback remains unchanged.

## Runtime and licence

The official `TTS==0.22.0` package runs in a dedicated Python 3.10 environment
under the isolated `Kyrion-Voice-Training` WSL distribution. Compatibility
pins are PyTorch 2.1.2 CUDA 12.1, Transformers 4.36.2, Tokenizers 0.15.2 and
Setuptools 80.9.0. No package was installed into `services/ai`.

The downloaded `tts_models/multilingual/multi-dataset/xtts_v2` snapshot is
licensed under the Coqui Public Model License. Its non-commercial terms were
explicitly accepted only for this local MVP benchmark. The model is not a
commercially distributable Kyrion choice. The TTS source package and model
licence are distinct.

The immutable reference is
`.run/velora-female-options/F_weiblich_klar.wav`, SHA-256
`d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09`.
Conditioning uses the complete 10.32-second reference and is computed once
before warm-up and measurement.

## Method

The runner consumes XTTS' native `inference_stream()` generator directly. Each
CUDA-synchronised generator yield is timestamped before its tensor is copied to
CPU. No batch WAV is split or replayed as fake chunks. The measured total covers
autoregressive generation and every incremental HiFi-GAN decode.

The matrix contains three warm repetitions of eight texts: the shared short,
medium, long, German-domain and English-domain phrases, German and English
punctuation/number phrases, and one longer natural German dialogue answer based
on the Phase 3.15 failure analysis. Sampling seeds are recorded by the runner.
The same matrix was run with 10- and 20-token chunks.

For each run the benchmark records first PCM, total generation time, audio
duration, RTF, chunk arrival intervals, delivery gaps relative to the previous
chunk's playable duration, simulated buffer depth, signal-boundary metrics,
process RSS and CUDA allocated/reserved memory. Audio is mono 24 kHz PCM16.

## Streaming results

The 20-token configuration is technically preferable. It trades roughly
300 ms more first-audio latency for substantially lower decoder overhead and a
larger sustained throughput margin.

| Configuration | Warm TTFA range | Worst P95 TTFA by phrase | RTF range | Long DE RTF | Dialogue DE RTF | Buffer underruns |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 tokens | 0.287–0.384 s | 0.383 s | 0.686–0.954 | 0.779–0.809 | 0.823–0.954 | 0/24 |
| 20 tokens | 0.523–0.724 s | 0.714 s | 0.632–0.787 | 0.675–0.706 | 0.668–0.705 | 0/24 |

For 20 tokens, the median chunk-arrival interval across per-run medians is
0.618 seconds; per-run P95 intervals range from 0.600 to 0.818 seconds. Every
next chunk arrives before the preceding chunk's audio is consumed: worst
delivery gap is -0.092 seconds, median of per-run median gaps is -0.306 seconds.
Minimum simulated buffer depth after playback begins is 0.218 seconds. This
configuration passes the required long-form RTF below 0.90 and continuously
generates faster than playback in every measured turn.

Warm 20-token results by phrase:

| Phrase | TTFA P95 | Mean / worst RTF | Mean total generation | Underruns |
| --- | ---: | ---: | ---: | ---: |
| Short DE | 0.611 s | 0.685 / 0.722 | 5.912 s | 0/3 |
| Domain DE | 0.571 s | 0.656 / 0.676 | 4.930 s | 0/3 |
| Domain EN | 0.647 s | 0.716 / 0.765 | 2.889 s | 0/3 |
| Medium DE | 0.714 s | 0.702 / 0.756 | 4.922 s | 0/3 |
| Long DE | 0.575 s | 0.690 / 0.706 | 6.661 s | 0/3 |
| Numbers DE | 0.627 s | 0.737 / 0.787 | 5.327 s | 0/3 |
| Numbers EN | 0.665 s | 0.668 / 0.709 | 3.821 s | 0/3 |
| Dialogue DE | 0.570 s | 0.685 / 0.705 | 7.942 s | 0/3 |

## Resources and stability

The warm 20-token matrix peaks at 2,173.8 MiB CUDA allocated, 2,382 MiB CUDA
reserved and 2,327.3 MiB process RSS. No sample clips and DC offset remains
negligible. The largest chunk-boundary sample jump is 0.147, compared with the
ordinary within-waveform P99 jumps recorded in the raw data; direct listening
is still authoritative for boundary continuity.

CUDA reservation rises in two bounded steps from 2,314 to 2,382 MiB. Process
RSS, however, rises from 2,113.3 MiB on turn one to 2,327.3 MiB on turn 24.
This 214 MiB monotonic increase does not satisfy the acceptance requirement for
twenty sequential turns with no increasing RAM allocation. The spike is already
a quality no-go, so no longer soak or allocator investigation is justified.

The measured standalone XTTS allocation would leave more than 1 GiB of the
8 GiB physical GPU free under the observed desktop/LLM load, but this is not a
controlled concurrent-residency certification and is not used to reverse the
decision.

## Audio quality

Faster-Whisper `small/int8` final transcription is used only as an objective
intelligibility probe; it does not replace listening:

| Input | Probe transcript / assessment |
| --- | --- |
| Short DE | Correct `Ich bin Velora.`, followed by long unintelligible pseudo-speech — fail |
| Domain DE | `Velora, schalte bitte die Desk, Lamp im Gaminraum ein.` — identity passes, room pronunciation fails |
| Domain EN | `Villora, turn on the desk lamp in the gaming room please.` — assistant identity fails |
| Medium DE | Exact words — pass |
| Long DE | Exact words apart from punctuation — pass |
| Numbers DE/EN | Meaning and numbers preserved — pass |
| Dialogue DE | Exact words apart from punctuation — pass |

All retained outputs have zero clipped samples. The short-run failure occurs in
all three measured generations: 5.29, 9.71 and 10.63 seconds of audio for a
three-word sentence. This is not an isolated listening preference. It violates
correctness and makes total-time/RTF figures for short text misleadingly look
acceptable because XTTS generates excess playable audio.

## Provisional outcome and evidence

Do not build a provider adapter or connect Core. A later focused short-output
termination spike was explicitly authorised and supersedes the earlier frozen
decoder decision; see `2026-08-11-xtts-v2-short-de-termination-spike.md`. XTTS
remained a candidate while the isolated guard path was evaluated. The later
live-generator guard failed the real-time gates and records the current no-go
in `2026-08-11-xtts-v2-live-generator-guard-spike.md`. Any future candidate
must still pass the shared
[`streaming TTS acceptance criteria`](../voice-tts-spike-acceptance.md).

Reproducible runners in Git:

- `.run/xtts_v2_streaming_benchmark.py`
- `.run/transcribe_tts_quality.py`

Private evidence outside Git:

- `E:/Kyrion/Data/voice-training/xtts-v2-velora-benchmark/results-chunk-10.json`
- `E:/Kyrion/Data/voice-training/xtts-v2-velora-benchmark/results-chunk-20.json`
  (SHA-256 `19364682231077c5e2f0ce54fd601670145c297502d3aa395916d9a656ae473c`)
- `quality-transcripts.json` and the corresponding private listening WAV files
  in the same directory
