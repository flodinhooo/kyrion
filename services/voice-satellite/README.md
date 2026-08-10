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
persisting audio. Streaming STT, a PCM downlink and interruption remain later
slices.

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

The reproducible local training configuration and its E:-drive storage boundary
are documented in [`training/README.md`](training/README.md). Training artifacts,
datasets, caches and generated speech remain outside the repository.

The first deployment is a non-privileged `systemd --user` service. The tracked
unit in [`deploy/kyrion-voice-satellite.service`](deploy/kyrion-voice-satellite.service)
reads an explicit JSON configuration from
`~/.config/kyrion/voice-satellite.json`. A model remains a test candidate until
its real-room metrics satisfy the acceptance criteria.
