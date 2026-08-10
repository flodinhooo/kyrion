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

## Physical acceptance

The real Raspberry Pi acceptance passed against Core on `192.168.1.107:8080`:

- three consecutive 20-second captures each delivered 250 ordered 80 ms frames
  and 640,000 PCM bytes;
- the calibrated reference run measured 2 ms first-frame and 12 ms maximum
  satellite-to-Core latency;
- Core working set remained 309.6-309.7 MiB and private memory remained
  411.2-411.3 MiB across two repeated full captures;
- an invalid Satellite token returned HTTP 401;
- explicit cancellation completed with `cancelled` and no later audio;
- an intentionally broken chunked upload failed without accepting a terminal
  result;
- a fresh turn on the same session succeeded immediately after that disconnect.

Windows and Pi wall clocks differed by roughly 294 ms despite both reporting
NTP synchronisation. The session-open response now carries Core time and the
Satellite applies a conservative per-session offset to capture timestamps.
Core retains signed latency values rather than silently clamping clock errors
to zero.

Phase 3.1 is accepted. Phase 3.2 may now add CPU-int8 streaming STT as a new
separately measured slice. TTS downlink, playback buffering and barge-in remain
out of scope.
