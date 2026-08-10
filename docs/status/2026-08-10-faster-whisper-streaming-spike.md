# Faster-Whisper streaming STT spike — 2026-08-10

## Scope

This isolated Phase 3.2 spike evaluates bounded rolling-window transcription
with the already installed Faster-Whisper 1.2.1 `small` model on CPU `int8`.
It does not connect the accepted PCM uplink to the AI service and does not
change Core, dialogue routing, TTS, playback or barge-in.

The spike resamples mono PCM16 reference WAV files to 16 kHz float PCM, keeps a
maximum 15-second rolling window and re-decodes without previous-text
conditioning. The model is loaded and warmed before measurements.

## Result

An 800 ms update interval fails the real-time throughput gate. Warm decode
calls took 1.45-1.71 seconds, so requests would queue and increasingly lag
behind incoming audio.

A 1,600 ms interval is viable as the current prototype candidate:

| Input | Duration | First partial decode | Final decode | Final text |
| --- | ---: | ---: | ---: | --- |
| Velora greeting | 2.64 s | 1.457 s | 1.490 s | `Hey Flo, womit kann ich dir behilflich sein?` |
| Velora live test | 2.40 s | 1.396 s | 1.428 s | `Guten Abend, ich bin bereit.` |
| Velora F test | 2.00 s | 1.408 s | 1.367 s | `Ich bin Velora.` |

Every decode stayed below the 1.6-second update interval and every final German
transcript was correct. The first two inputs produced useful partial text after
1.6 seconds of available audio. The shortest input already had its correct
final wording at the first update.

## Real Delock microphone gate

The owner recorded one independent 150-second session through the production
Delock microphone: 12 German commands, eight English commands, silence and
ordinary non-speech sounds. The immutable private source remains outside Git
under `E:/Kyrion/Data/voice-training/phase32-stt/` with SHA-256
`FE18C69A546A3F52B01BCC04409147FDF0E6518AFAFEC97ABA4AE771AD797537`.
Pause-based segmentation produced 20 speech clips and six non-speech clips.

With the explicit session locale and VAD enabled, `small/int8` produced usable
or correct final meaning for 16 of 20 speech clips. All six silence/noise clips
returned empty text. Automatic per-clip language detection had previously
misclassified one English command as Welsh and hallucinated Sinhala text for a
noise clip, so production must retain the explicit Core-owned session locale
and upstream VAD boundary.

The remaining weaknesses were concentrated around the assistant/device terms
`Velora`, `Gamingraum`, one English availability question and `desk lamp`.
These are not safe to silently correct inside STT. Later target resolution may
use the owner-visible device catalogue, but Core must still clarify ambiguity
rather than guessing.

Real 1,600 ms rolling-window calls on `small/int8` usually took 1.36-1.58
seconds. A difficult final German decode reached 1.98 seconds. When end of
speech arrived shortly after an in-flight partial, the non-cancellable final
decode waited and end-of-speech-to-final latency reached roughly 2.4-2.9
seconds. Final recomputation did correct meaningful hypotheses such as
`desk clamp` to `desk lamp`, so simply accepting the last partial is unsafe.

The multilingual `base/int8` comparison completed each decode in roughly
0.41-0.49 seconds and sustained 800 ms updates, but materially damaged German
command accuracy and longer-sentence meaning. It is rejected.

## Decision

Do not integrate either rolling-window design. `base/int8` fails quality;
`small/int8` cannot reliably finish a partial before the next update and its
full-window recomputation can delay the authoritative final transcript. The
existing bounded final-utterance `small/int8` path remains the honest fallback.

Phase 3.2 is therefore **FAIL for Faster-Whisper rolling-window streaming**,
not a failure of the accepted PCM transport. Before changing Core or AI
contracts, evaluate a genuinely incremental local STT runtime that retains
decoder/encoder state, coalesces rather than queues partial work, supports
explicit German and English locale, emits partial/final distinction and
cancels promptly. Faster-Whisper may remain the final-transcript reference
during that comparison.

## Evidence

- `.run/faster_whisper_streaming_spike.py`
- `.run/phase32-faster-whisper-streaming.json`
- `.run/phase32-faster-whisper-streaming-1600ms.json`
- private `batch-transcripts.json`, `locale-vad-transcripts.json` and rolling
  measurements under `E:/Kyrion/Data/voice-training/phase32-stt/`
