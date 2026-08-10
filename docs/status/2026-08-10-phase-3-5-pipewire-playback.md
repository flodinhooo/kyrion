# Phase 3.5 PipeWire PCM playback — 2026-08-10

## Scope

This slice adds only a raw-PCM Satellite sink for the accepted Phase 3.4 jitter
buffer. It remains disconnected from TTS providers, the production dialogue
runtime and barge-in.

`PipeWirePcmSink` starts one argument-safe `pw-play` process per turn with an
explicit target, raw signed 16-bit mono 24 kHz format and bounded latency. It
writes only complete accepted 160 ms frames. Completion closes stdin and waits
for a clean process exit; cancellation terminates the process and prevents all
later writes for the old turn.

Automated tests use a fake process and cannot emit audio. The silent physical
path passed with 20/20 frames, no drop and a two-frame peak. After a
bounded 50 ms graceful-process window, cancellation stopped 59 ms after the
test signal and wrote no queued old-turn frame. Audible Pebble confirmation
with a fixed quiet 440 Hz fixture remains open.

The first audible streaming tone had short dropouts although software counters
reported no underflow. The owner then confirmed twice that the same fully
buffered PCM played perfectly. This isolates the defect to just-in-time writes
between the application buffer and `pw-play`, not the transport, Bluetooth link
or Pebble hardware. The downstream sink was therefore changed to receive the
complete two-frame prebuffer immediately before paced refill.

The corrected path was then heard twice by the owner and both runs sounded
fully correct without dropouts. Each delivered 10/10 frames and 76,800 PCM
bytes with a two-frame peak and no drop. Two later source frames missed the
application refill deadline, but the audio already primed into PipeWire covered
that delay and the owner heard no interruption. This counter is therefore named
`refill_deadline_misses`; it is not claimed as an audible PipeWire underflow.

Phase 3.5 is **PASS** for bounded synthetic playback and cancellation. This does
not yet connect a TTS provider or the production Dialogue Controller.
