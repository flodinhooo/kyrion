# Voice Satellite and Wake-Word Session — 2026-08-09

## Outcome

The Raspberry Pi voice hardware and first local wake-word path are operational.
The Delock USB microphone captures 16 kHz mono PCM16 audio and the Pebble V3
speakers play through the paired Bluetooth/PipeWire sink. A non-privileged
`systemd --user` Voice Satellite performs continuous local openWakeWord ONNX
inference without sending ambient audio off the Pi.

The deployed model is the safer second test candidate, not the most recent
experiment. Its SHA-256 is
`cf457d369d9353deb77b7dacd00a261b9544a2f748c0c62453278a93c7199115`.
The service was active at handoff and the same hash was verified on the Pi.
The original synthetic baseline remains beside it for rollback with SHA-256
`24009cadee35f3c3385b7a316cc2ac574b44e099c0d5333fdca4770930060b97`.

The post-wake dialogue is intentionally not implemented yet. Detection still
produces only a local structured log event. Bounded capture, authenticated
delivery, local STT, Core/assistant routing, local TTS and interruption remain
the next vertical slice after wake-word quality is accepted.

## Physical acceptance completed

- Delock microphone uses stable ALSA selector `hw:CARD=M20672,DEV=0`.
- Pebble V3 Bluetooth playback and reconnect were verified.
- A direct audio test was audible through the Pebbles.
- The first baseline live `Hey Velora` detection was logged at score `0.601`.
- The Voice Satellite runs as
  `~/.config/systemd/user/kyrion-voice-satellite.service` without root.
- Active configuration is `~/.config/kyrion/voice-satellite.json`.
- Active model is
  `~/.local/share/kyrion/voice-satellite/models/hey_velora.onnx`.
- Rollback model is
  `~/.local/share/kyrion/voice-satellite/models/hey_velora-baseline-20260808.onnx`.

## Private recording and data boundary

One 240-second Pi session was recorded, copied byte-for-byte to the E:-backed
private training store and split into 57 candidates. Human review labelled 51
complete `Hey Velora` positives, five `Velora`-only hard negatives (clips 7,
10, 18, 45 and 49), and one excluded start/noise clip.

The deterministic split contains 40 positive and four negative training clips,
plus an untouched holdout of 11 positive and one negative clip. Owner audio,
generated features, datasets and models remain outside Git under the dedicated
`Kyrion-Voice-Training` WSL distribution stored on E:. The repository contains
only reproducible scripts, configuration, tests and documentation.

## Candidate results and accepted decision

| Model | Synthetic recall | False positives/hour | Real positive holdout | Real `Velora` holdout | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline | 0.417 | 1.062 | 4/11 | rejected | rollback only |
| V2 | 0.389 | 0.354 | 5/11 | rejected | deployed test candidate |
| V3, strong real weighting | 0.300 | 0.796 | 11/11 | accepted incorrectly | rejected as overfit |
| V4, moderate positive/strong negative weighting | 0.332 | 0.265 | 11/11 | accepted at 0.5 | rejected as overfit |

V4 separated the one held-out partial phrase only at threshold `0.97`: all
11 real positives remained above it and the partial phrase fell below it.
However, only 4/3000 synthetic positives reached that threshold. This is
session-specific calibration, not general wake-word quality, and was correctly
rejected. V3 and V4 are archived as diagnostic candidates and were never
deployed. The E:-training workspace and the Pi both point to V2 at handoff.

## Reproducible tooling added

- `segment_recording.py`: segmentation with an unreviewed manifest.
- `label_recording.py`: applies explicit human labels to private clips.
- `prepare_real_examples.py`: deterministic train/holdout preparation.
- `build_real_features.py`: builds moderately augmented real features.
- `combine_features.py`: shuffles weighted general and real features.
- `run_openwakeword_training.py`: narrow upstream compatibility fixes.

Fifteen Voice Satellite tests pass, Ruff passes and `git diff --check` passes.
The final Pi service check returned `active` with the expected V2 checksum.

## Exact next-session order

1. Read this handoff, `docs/status/README.md`, `docs/status/TODO.md` and the
   Voice Satellite training README. Preserve unrelated Web changes.
2. Verify the Pi service and V2 checksum. Do not deploy V3 or V4 and do not
   report their 11/11 same-session result as generalisation.
3. Record at least 20–30 natural `Velora`-only utterances plus similar phrases
   and ordinary sentences containing `Velora`. Vary distance, level,
   orientation and pace.
4. Record a separate positive/negative set through at least one phone
   microphone. Keep device/session holdouts that never enter training.
5. Train V5 with explicit balance. Accept it only if complete-phrase recall
   improves, every independent `Velora` holdout remains rejected and general
   synthetic performance does not collapse.
6. Perform repeated physical Pi tests at the chosen threshold, including quiet,
   distant, fast and differently pronounced phrases and normal room audio.
7. After wake-word acceptance, implement the smallest bounded dialogue slice:
   local wake, acknowledgement tone, VAD-bounded capture, authenticated Core
   delivery, local STT, existing assistant path, local TTS and Pebble playback.

## Mobile direction

The architecture must not assume the Pi microphone. Each device performs local
wake detection and opens only a bounded post-wake session. A general model needs
independent data and holdouts across voices, rooms and microphone classes. A
device-specific calibration or optional personal verifier may be layered above
a general base model, but same-session accuracy must never be reported as
cross-device quality.
