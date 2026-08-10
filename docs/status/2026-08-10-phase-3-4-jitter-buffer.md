# Phase 3.4 Satellite PCM jitter buffer — 2026-08-10

## Scope

This slice begins a bounded Satellite-side buffer for the accepted Phase 3.3
160 ms PCM downlink. It remains disconnected from PipeWire/Pebble playback, all
TTS providers, the Dialogue Controller and barge-in.

## Initial software contract

`PcmJitterBuffer` is a single-producer, single-consumer queue for fixed 24 kHz
mono PCM16 frames. Its defaults are:

- two-frame / 320 ms prebuffer;
- eight-frame / 1.28 second hard capacity;
- blocking bounded backpressure rather than unbounded growth or silent drops;
- absolute playback pacing after prebuffer;
- explicit producer completion;
- cancellation that clears queued old-turn audio before returning;
- counters for received, consumed and discarded frames, refill deadline misses,
  backpressure waits and peak queue depth.

The consumer is a caller-supplied callback. No audio device is opened by this
class, so automated tests cannot accidentally produce speaker output.

## Physical acceptance

The silent Pi run connected the accepted Phase 3.3 downlink directly to this
buffer with a discard-only sink:

- all 125 frames / 960,000 bytes were received and consumed;
- elapsed time was 20.327 seconds including the 320 ms prebuffer;
- peak queue depth was exactly two frames;
- no frame was dropped and no refill deadline miss or backpressure wait occurred;
- cancellation consumed three frames, discarded the one queued old-turn frame
  and stopped without consuming later audio.

Phase 3.4 is **PASS** for the isolated jitter buffer. Actual PipeWire/Pebble
playback remains the next separately accepted slice.

## Evidence

- `services/voice-satellite/src/kyrion_voice_satellite/pcm_jitter_buffer.py`
- `services/voice-satellite/tests/test_pcm_jitter_buffer.py`
- `.run/phase34_pi_jitter_acceptance.py`
