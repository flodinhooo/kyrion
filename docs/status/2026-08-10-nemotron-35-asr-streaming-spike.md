# Nemotron 3.5 ASR streaming spike — 2026-08-10

## Scope

This isolated Phase 3.2 spike evaluates NVIDIA's
`nemotron-3.5-asr-streaming-0.6b` through NeMo-Speech.cpp. It does not integrate
with Core or the AI service and does not replace the existing bounded
Faster-Whisper `small/int8` final-transcript path.

The comparison reuses the immutable private 150-second Delock microphone
recording and its existing pause-based segmentation: 20 speech clips (12
German, eight English) and six silence/ordinary-noise clips. No generated or
clean reference audio is mixed into the result. The source remains outside Git
under `E:/Kyrion/Data/voice-training/phase32-stt/`, with SHA-256
`FE18C69A546A3F52B01BCC04409147FDF0E6518AFAFEC97ABA4AE771AD797537`.

## Runtime

The official NeMo-Speech.cpp 1.0.0 source was built for CPU in the isolated
`Kyrion-Voice-Training` WSL distribution. The exact source revision was
`5be7bfb104802131e61fe679b3f1401b27270216`. The official 708 MiB Q8 GGUF
`nemotron-3.5-asr-streaming-0.6b.q8_0.gguf` was loaded once by the local HTTP
server. German and English clips used explicit `de-DE` and `en-US` session
locales respectively.

The benchmark sends little-endian 16 kHz mono PCM16 over the runtime's realtime
WebSocket at wall-clock rate. It records append-only partial events, the final
event, process-tree CPU and resident memory. Each clip is committed immediately
after its last sample. The server is stopped after every chunk-size matrix.
Nothing listens outside WSL loopback and no audio leaves the machine.

NeMo-Speech.cpp is Apache-2.0-licensed. The model uses NVIDIA's Open Model
Development and Work License 1.1. This is sufficient for the spike but remains
a separate distribution/commercial-policy review item if the model is ever
shipped as part of Kyrion.

## Streaming results

All three runs produced the same final words and raw word-error count. The raw
WER uses simple case/punctuation normalization and therefore penalises harmless
number formatting such as `fünf und dreißig` versus `fünfunddreißig`.

| PCM chunk | Raw WER | First usable partial, median (range) | Partial interval, median / P95 | EOS to final, mean / P95 / max | Noise hallucinations |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 160 ms | 11.2% | 1.120 s (0.881–1.761) | 0.163 / 0.296 s | 0.454–0.486 / 0.542–0.602 / 0.707 s | 0/6 |
| 320 ms | 11.2% | 1.086 s (0.769–1.911) | 0.320 / 0.340 s | 0.550 / 0.716 / 0.731 s | 0/6 |
| 560 ms | 11.2% | 0.982 s (0.757–1.681) | 0.462 / 0.689 s | 0.592 / 0.821 / 0.916 s | 0/6 |

The 160 ms matrix was repeated after the final script cleanup. Its transcripts,
WER and hallucination count were identical; the table reports the range of the
two mean final latencies and the worse observed maximum. The first-partial clock
starts at the first streamed WAV sample, including each
clip's retained leading room tone. Nineteen of 20 speech clips produced a
partial; the missed `Velora` greeting also produced an empty final. A shorter
transport chunk does not make speech observable earlier, but 160 ms gives much
more frequent updates and the lowest, most consistent final latency. It is the
technical latency sweet spot in this implementation.

## Recognition quality

Manual command-meaning review gives Nemotron usable/correct meaning for 16 of
20 sentences, equal to the existing `small/int8` final baseline rather than a
clear win. Raw normalized WER is lower than the baseline's 13.8%, but that
aggregate hides regressions in the explicitly important vocabulary:

| Focus | Nemotron final | Faster-Whisper `small/int8` final | Assessment |
| --- | --- | --- | --- |
| German `Velora` | empty | `Fedora` | neither passes; Nemotron regresses to no command |
| English `Velora` | `V oro` | `Avalora` | neither preserves the assistant name |
| `Gamingraum` command | `Gaming Room` | `Gaming-Ruhr` | neither preserves the configured German room name |
| German correction | `Nein, nicht das Wohnzimmer. Ich meinte den Gamingraum.` | exact intended wording | both preserve correction intent |
| English correction | exact intended wording | exact intended wording | both pass |
| `desk lamp` | `desk clamp` and `land next to the window` | final corrects to `desk lamp` and `lamp next to the window` | Nemotron regresses materially |

Additional Nemotron errors include `Welche gereit ... erreichba`, command verb
`schaute` instead of `schalte`, and an extra `leicht` before `Licht`. Its strong
results include the long English command, the ordinary stop commands and both
spoken correction-intent sentences.

The fixed comparison recording contains complete correction sentences (`Nein,
nicht ... ich meinte ...` / `No, I meant ... not ...`), not the exact interrupted
false start `Wohn– nein, Gamingraum`. Nemotron emits append-only deltas and
correctly completes the two available correction intents; revision of an
already emitted false-start token is not established by this dataset. Creating
a synthetic splice or adding a new recording would violate the requested exact
comparison basis, so the result does not claim that behaviour.

## Resources

The CPU backend used no model VRAM. CPU percentages are process-tree totals, so
100% represents one fully occupied logical CPU.

| PCM chunk | Mean CPU | P95 CPU | Peak CPU | Mean RSS | Peak RSS | Model VRAM |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 160 ms (two runs) | 132–139% | 188% | 426% | 936 MiB | 936 MiB | 0 MiB |
| 320 ms | 137% | 188% | 412% | 935 MiB | 936 MiB | 0 MiB |
| 560 ms | 138% | 188% | 433% | 938 MiB | 939 MiB | 0 MiB |

Memory remained flat across the sequential 26-clip runs. The short CPU peaks
are model work across several threads; sustained load is approximately 1.3–1.4
logical cores on this workstation.

## Decision

Nemotron 3.5 demonstrates the incremental runtime properties the rolling
Faster-Whisper spike lacked: stable append-only partials, no queued full-window
redecode, no silence/noise hallucinations with explicit locale, and comfortably
sub-second final latency on CPU. The 160 ms transport chunk is preferred over
320 and 560 ms for this runtime.

The benchmark is nevertheless **NO-GO for integration**. It ties the manual
20-sentence quality gate, misses `Velora` and `Gamingraum`, and materially loses
the `desk lamp` final correction that `small/int8` gets right. That is not the
clear benchmark win required to plan a Voice Pipeline integration. Core, AI and
the existing Faster-Whisper path remain unchanged.

This result is frozen. Do not run further Nemotron tuning or word-boosting
experiments, plan a Core integration, or replace the Faster-Whisper baseline.
Future candidates are judged by the shared
[`streaming STT acceptance criteria`](../voice-stt-spike-acceptance.md), which
weight domain identity and command meaning more strongly than aggregate WER.

## Evidence

- `.run/nemotron_streaming_benchmark.py`
- private `nemotron-cpu-160.json`, `nemotron-cpu-160-verification.json`,
  `nemotron-cpu-320.json` and `nemotron-cpu-560.json` under
  `E:/Kyrion/Data/voice-training/phase32-stt/`
- corresponding private server logs beside those result files
- baseline `locale-vad-transcripts.json` in the same private directory
