# Phase 3.3 PCM downlink transport — 2026-08-10

## Scope

This slice begins the provider-neutral Core-to-Satellite audio transport after
Phase 3.2 closed without a streaming-STT integration. It uses deterministic
synthetic silence only. It does not connect Qwen or Chatterbox, change the
Dialogue Controller, play audio, implement a jitter buffer or add barge-in.

## Software prototype

Core exposes an authenticated prototype NDJSON response for an active voice
session. The request supplies a turn ID and a 160-ms-aligned duration bounded
to 20 seconds. The response contains:

- one `start` event declaring mono 24 kHz PCM16 and a 160 ms frame duration;
- ordered `audio` events scoped by session and turn, with sequence and Core
  production timestamp;
- one `complete` event with authoritative frame and byte totals.

Core validates authentication, active-session ownership and duration before
returning the streaming response. The synthetic source emits one 7,680-byte
frame every 160 ms and retains no accumulated audio. This pacing belongs only to
the transport fixture; a later provider will supply frames at its measured
generation cadence.

The isolated Satellite client validates every event before passing PCM to a
caller-supplied sink. It rejects scope mismatch, sequence gaps, invalid format,
invalid frame size, excessive event/frame counts and mismatched completion
totals. Local cancellation closes consumption before any later frame reaches
the sink. No production runtime mode calls this client yet.

## Automated verification

- Core service tests cover authentication-before-audio, ordering, byte totals
  and invalid duration.
- Satellite tests cover valid delivery, sequencing, cross-turn rejection,
  cancellation and bounded/misaligned duration.

The complete Core and Satellite test suites pass, as does the Core bootable JAR
build.

## Physical acceptance

The real Raspberry Pi acceptance passed against Core at `192.168.1.107:8080`.
An initial 80 ms experiment exposed additive flush overhead: two of three
deadline-paced runs took 20.72 and 22.67 seconds and showed stalls up to 1.67
seconds. The LAN itself remained healthy, with approximately 0.5 ms TCP connect
time and typical 4–6 ms Core health responses. The 80 ms transport framing was
therefore rejected rather than hiding the stalls behind a future jitter buffer.

The accepted 160 ms framing produced four stable 20-second runs:

| Run | Frames | PCM bytes | Elapsed | Calibrated first / maximum latency |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 125 | 960,000 | 19.882 s | 143 / 168 ms |
| 2 | 125 | 960,000 | 19.858 s | 152 / 169 ms |
| 3 | 125 | 960,000 | 19.860 s | 154 / 170 ms |
| verification | 125 | 960,000 | 19.850 s | 164 / 176 ms |

Windows and Pi clocks still differ by roughly 292–297 ms. The one-way latency
uses the same conservative session calibration as Phase 3.1; elapsed duration
and the 12–27 ms within-run latency spread are the stronger transport evidence.

Client cancellation admitted one frame, delivered no later frame to the sink
and returned about 162 ms after cancellation was set. A fresh two-frame turn
succeeded immediately afterward. A wrong Satellite token was rejected. Core
working set stayed between 323.7 and 325.4 MiB and private memory between 369.5
and 371.3 MiB during the additional full run.

Phase 3.3 is **PASS** for the isolated transport. This does not approve a TTS
provider, playback or dialogue integration.

## Evidence

- `services/core/src/main/kotlin/dev/kyrion/core/voice/VoicePcmDownlink.kt`
- `services/core/src/test/kotlin/dev/kyrion/core/voice/VoicePcmDownlinkServiceTest.kt`
- `services/voice-satellite/src/kyrion_voice_satellite/pcm_downlink.py`
- `services/voice-satellite/tests/test_pcm_downlink.py`
- `.run/phase33_pi_downlink_acceptance.py`
