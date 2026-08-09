# Velora F voice profile

This directory describes Velora's provider-independent qualitative reference
voice. The canonical reference audio remains the tracked file
`.run/velora-female-options/F_weiblich_klar.wav` at the repository root so that
the original Git object is not duplicated or rewritten.

The canonical WAV is immutable. Verify its SHA-256 against `manifest.json`
before deriving provider conditioning. Never normalise, trim, resample or
overwrite it in place. Benchmark and provider-specific outputs belong in their
own directories and are not replacements for the reference.

`providers/` records reproducibility information for derived conditioning.
Runtime caches may live outside Git because they can be large or
version-specific, but they must identify this profile and reference checksum.
