# Short-TTS provider benchmark — 2026-08-11

## Status and boundary

Stage 1 is complete and **pending manual review**. Stage 2 and Stage 3 have not
started. No candidate is integrated, no provider/default routing is changed,
and Core, Satellite and the Fixed/Template/Dynamic implementation are outside
this benchmark's change scope.

XTTS v2 remains the opt-in quality reference for normal and longer answers. Its
Short EOS, VAD, guard and punctuation experiments are closed and were not
repeated.

## Inventory and candidate selection

| Candidate | Why it remains relevant | Local state | DE/EN | Streaming in measured path | Voice identity path | Hardware | Licence status | Stage decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Chatterbox Multilingual 0.1.7 | Existing operational clone-capable batch fallback; Short reliability had not been isolated | Installed and measured | DE and EN supported | No; complete WAV only | Zero-shot conditioning from immutable Velora-F reference | RTX 2070; about 3.5 GiB measured peak allocation | Installed package and repository declare MIT | Stage 1 complete, manual gate pending |
| Piper 1.6.0, `de_DE-kerstin-low` | Deterministic-style CPU latency/termination baseline for fixed-shape Shorts | Installed and measured | Installed model is DE only | `PiperVoice.synthesize()` yields audio chunks; current single-sentence cases produced first audio near completion | No current Velora clone; a separately trained voice would be required | CPU, 16 kHz low-quality model | Runtime GPL-3.0-or-later; model card states CC0 dataset, but model-weight redistribution needs explicit verification | Stage 1 complete, manual gate pending |
| Qwen3-TTS 0.6B/1.7B | Strong Velora identity and DE/EN cloning | Installed, prior benchmark retained | DE/EN | Custom internal spike only | Exact cached Velora-F prompt | 0.6B FP32 leaves only 796 MiB combined margin; 1.7B first PCM about 2.3 s | Apache-2.0 recorded from installed package/model evidence | C — do not repeat |
| Fun-CosyVoice3 0.5B | Official clone/streaming candidate previously selected | Installed, prior proof retained | DE/EN proof generated | Technically streaming, but usually one complete chunk | Velora-F zero-shot conditioning | 5.0 GiB peak; 4.2–5.4 s first PCM | Repository evidence recorded as Apache-2.0; downloaded-artifact review remains required before distribution | C — prior no-go, do not repeat |

Kokoro and F5-TTS were considered only as possible new downloads. Neither was
selected for Stage 1: the available baseline evidence did not establish the
required combination of German Short quality and Velora-compatible cloning.
The external primary-source lookup returned no usable content in this session,
so their current code/model-weight licences and redistribution terms remain
explicitly unverified. No package or model was downloaded on assumptions.

## Reproducible corpus

`.run/short_tts_corpus.json` defines 25 bounded cases:

- Stage 1: five DE smoke cases and seven runs, including three fixed-seed
  requests for `Ich bin Velora.`;
- Stage 2: fourteen extended DE/EN cases covering acknowledgement, rejection,
  greeting, command success/failure, device/room/person names, numbers, time,
  percentage and mixed `Desk Lamp` language;
- Stage 3: six Category-B-style DE/EN templates with three runs each for room
  light success, device unavailability and updated-device count.

The isolated `.run/short_tts_provider_benchmark.py` records engine/version,
model/configuration, seed support, corpus/reference hashes, WAV hashes, runtime
context, load/conditioning time, first exposed audio, total synthesis time,
RTF, process CPU/RAM and GPU peak allocation where applicable. Every generated
run starts as `pending_manual_review`.

Private outputs are stored under:

```text
E:/Kyrion/Data/voice-training/short-tts-provider-benchmark/
  piper/stage-1/
  chatterbox/stage-1/
  stage-1-offline-asr.json
```

## Stage 1 measurements

### Piper

- model load: 2.342 s;
- warm first exposed audio / complete synthesis: 0.028–0.077 s;
- warm RTF: 0.029–0.040;
- first identity run after load: 0.317 s, RTF 0.275;
- CPU-only, with measured multi-core process use;
- all outputs are mono 16 kHz;
- the three nominal identity repetitions have different WAV hashes and
  durations of 1.152, 1.072 and 1.088 s; this API/model does not accept a seed;
- the runtime repeatedly warned about missing combining phoneme `U+0327`.

### Chatterbox

- model load: 49.144 s;
- Velora-F conditioning: 8.023 s;
- batch first playable equals completion: 2.044–4.686 s;
- RTF: 1.172–1.603, so every Stage-1 run generated slower than playback;
- peak allocated VRAM: 3,479–3,519 MiB;
- all outputs are mono 24 kHz;
- the three identity repetitions vary from 1.28 to 3.08 s of audio;
- the runtime forced EOS for token repetition or its internal long-tail
  detector during several runs.

These Chatterbox internals are observations, not proof of audible failure.

## Offline ASR hint — not ground truth

Faster-Whisper `small/int8` was run once on complete Stage-1 WAVs only. It is not
a runtime guard and is not part of any proposed Short provider path.

- Piper produced no recognized extra continuation, but `Velora` was recognized
  as `Veloora`/`Veloror` in all three identity runs and `Gamingraum` as
  `Gaming-Rom`.
- Chatterbox matched six expected texts; its domain sample was recognized as
  `Die Desklampe im Gamingraum ist eingeschaltet. Eingeschaltet.`

All correctness, truncation, fantasy speech, pronunciation, prosody and voice
identity fields remain `pending_manual_review` regardless of this hint.

## Manual Stage-1 gate

Listen to all seven WAVs per provider, with particular attention to:

1. the three `de.identity` repetitions;
2. Piper pronunciation of `Velora`, `Desk Lamp` and `Gamingraum`;
3. Chatterbox's varying identity duration;
4. whether the Chatterbox domain sample audibly repeats `eingeschaltet`;
5. Piper versus Chatterbox naturalness and Velora-F identity.

Stage 2 is permitted only for a candidate whose outputs terminate cleanly,
contain the complete requested text and have adequate German intelligibility.
Piper cannot enter the English part of Stage 2 without a separately selected
and licence-verified EN model. Chatterbox's 2.0–4.7 s batch latency already
misses the intended sub-second Short target, so further work is justified only
if the owner considers its identity/quality valuable as a non-winning baseline.

## Interim decision table

| Candidate | Short reliability | First playable | RTF | DE | EN | Voice identity | Resources | Licence | Decision |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| Piper Kerstin low | `pending_manual_review`; no ASR-indicated extra speech | 0.028–0.077 s warm | 0.029–0.040 warm | pronunciation review pending | unavailable in installed model | expected low; review pending | CPU, low RAM/16 kHz | runtime known; model redistribution verification open | B pending listening |
| Chatterbox Multilingual | `pending_manual_review`; one ASR-indicated repetition | 2.044–4.686 s batch | 1.172–1.603 | review pending | supported, not yet benchmarked | Velora clone; review pending | ~3.5 GiB peak VRAM | MIT recorded | B pending listening; latency already fails target |
| Qwen 0.6B/1.7B | prior work retained | ~2.3 s best accepted 1.7B stream | long generation slower than playback | accepted sample quality | accepted sample quality | strong | high VRAM/custom path | Apache-2.0 recorded | C |
| CosyVoice3 0.5B | prior proof retained | 4.2–5.4 s | ~0.94–1.52 | generated | generated | not promoted to listening gate | ~5.0 GiB peak VRAM | artifact review incomplete | C |

No winner is selected at Stage 1.

