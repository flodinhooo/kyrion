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

## Decision

Do not integrate the 800 ms design. Retain 1,600 ms as the next candidate, but
do not call Phase 3.2 accepted yet. The current evidence uses clean generated
speech and short utterances. A provider contract needs an independent real
Delock-microphone set with ordinary German and English speech, silence/noise,
longer utterances, partial-hypothesis correction and cancellation measurements.

Only after that gate passes should Core forward bounded PCM to an AI-service
streaming STT provider. The transport must coalesce updates rather than queue
concurrent decodes, cap the rolling window, mark partial versus final text and
discard all state on cancellation.

## Evidence

- `.run/faster_whisper_streaming_spike.py`
- `.run/phase32-faster-whisper-streaming.json`
- `.run/phase32-faster-whisper-streaming-1600ms.json`
