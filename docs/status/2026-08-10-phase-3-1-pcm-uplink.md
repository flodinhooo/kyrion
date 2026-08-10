# Phase 3.1 PCM uplink prototype — 2026-08-10

## Outcome

The bounded software slice is implemented. An already-woken Voice Satellite
can open its existing authenticated Core-owned session and upload continuous
16 kHz mono PCM16 frames through one chunked HTTP/NDJSON request. The legacy
batch dialogue remains the default and is unchanged. No STT, TTS downlink,
playback buffer, Qwen provider integration or barge-in was added.

## Contract and boundaries

Every event carries `sessionId` and `turnId`. A `start` event declares sample
rate and channel count. Each `audio` event repeats the format and carries a
zero-based monotonically increasing sequence, capture epoch timestamp and one
base64-encoded PCM frame. `complete` and `cancel` are terminal events.

Core authenticates the Satellite credential and active session before reading
PCM. It accepts only 16 kHz mono PCM16, limits one event to 8,192 characters,
one frame to 100 ms, and one request to 60 seconds of PCM. Input is read and
validated incrementally; Core never accumulates or persists the full audio.
It returns frame count, PCM byte count, sequence range, first-frame latency and
maximum frame latency. A stream ending without a terminal event is rejected as
a disconnect.

The Satellite's existing 80 ms ALSA frames map directly to uplink frames. The
opt-in `dialogue_mode: "pcm-uplink"` stops at the configured utterance maximum.
The default remains `batch` until physical acceptance succeeds.

## Automated verification

- Satellite Ruff: pass.
- Satellite tests: 29 passed, including ordered framing, authentication header,
  cancellation, invalid capture data, rejection handling and fresh sequence
  state after reconnect.
- Core Phase 3.1 tests: pass, covering ordering and timing, sequence gaps,
  missing terminal events, cancellation, authentication and reconnect state.
- Core `bootJar`: pass.
- The complete Core test task compiled and ran 28 tests; its only failure was
  the pre-existing Testcontainers integration test because Docker was not
  running.

## Remaining acceptance gate

Run the opt-in mode on the real Raspberry Pi against Core with synchronised
clocks. Record one-way latency, force authentication failure, interrupt a live
request, break and restore the connection, and verify that memory remains
bounded. Do not begin streaming STT until this physical gate passes.
