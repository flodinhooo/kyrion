# Kyrion Voice Satellite

This service owns local wake-word inference and bounded audio sessions on a
Kyrion satellite. It does not execute device commands and does not continuously
send or persist room audio.

The runtime consumes mono 16-bit 16 kHz PCM from one explicit ALSA hardware
selector in 80 ms frames. An owner-supplied, versioned ONNX model is evaluated
locally. After a positive score, `dialogue_mode` selects the working legacy
`batch` dialogue or the bounded Phase 3.1 `pcm-uplink` prototype. The prototype
streams authenticated typed NDJSON events to Core, which verifies the active
session, turn scope, format and monotonically increasing sequence without
persisting audio. Streaming STT and interruption remain later slices. Phase
3.3 contains an isolated PCM downlink transport prototype: an authenticated
active satellite session may request bounded deterministic 24 kHz mono PCM16
frames from Core. The satellite validates session/turn scope, format, sequence
and totals and passes frames only to a caller-supplied sink. It is not connected
to the runtime, Qwen, PipeWire/Pebble playback or a jitter buffer.

The prototype is opt-in:

```json
{
  "dialogue_mode": "pcm-uplink"
}
```

It stops after the configured `utterance_max_seconds` and records the first and
maximum satellite-to-Core frame latency. The clocks must be synchronised for
those one-way measurements to be meaningful. Keep `batch` selected until the
physical Pi-to-Core acceptance is complete.

The intended production wake phrase is `Hey Velora`. The custom model is not
committed until its training data provenance, license and real-room false
accept/reject measurements are recorded.

## Dialogue session behaviour

Say `Hey Velora` to open a fresh Core-owned voice session. After Velora answers,
the satellite listens for a bounded follow-up window, so the next command can
be spoken directly without repeating the wake phrase. After inactivity closes
that window, use `Hey Velora` again.

Repeating `Hey Velora` during an active follow-up window is also valid. Core
closes the previous session with reason `restart`, and the satellite immediately
opens and acknowledges a new session. The deployed German STT's observed
`Hey Willorra` and `Hey Fedora` transcriptions are treated as wake-phrase
restarts rather than chat messages. A failed Core stream is logged, but the
satellite returns to local wake-word detection instead of terminating the
runtime.

The reproducible local training configuration and its E:-drive storage boundary
are documented in [`training/README.md`](training/README.md). Training artifacts,
datasets, caches and generated speech remain outside the repository.

The first deployment is a non-privileged `systemd --user` service. The tracked
unit in [`deploy/kyrion-voice-satellite.service`](deploy/kyrion-voice-satellite.service)
reads an explicit JSON configuration from
`~/.config/kyrion/voice-satellite.json`. A model remains a test candidate until
its real-room metrics satisfy the acceptance criteria.
