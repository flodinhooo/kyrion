# Kyrion Voice Satellite

This service owns local wake-word inference and bounded audio sessions on a
Kyrion satellite. It does not execute device commands and does not continuously
send or persist room audio.

The first runtime consumes mono 16-bit 16 kHz PCM from one explicit ALSA
hardware selector in 80 ms frames. An owner-supplied, versioned ONNX model is
evaluated locally. A positive score currently produces only a structured log
event; capture-after-wake, authenticated Core delivery, STT, TTS and
interruption are subsequent slices.

The intended production wake phrase is `Hey Velora`. The custom model is not
committed until its training data provenance, license and real-room false
accept/reject measurements are recorded.

The reproducible local training configuration and its E:-drive storage boundary
are documented in [`training/README.md`](training/README.md). Training artifacts,
datasets, caches and generated speech remain outside the repository.
