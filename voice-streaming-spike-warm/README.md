# Qwen 1.7B Velora F streaming spike

This directory contains the warm-runtime proof of concept for incremental
Qwen3-TTS-12Hz-1.7B codec-frame decoding. It is an isolated experiment and is
not connected to Kyrion Core, the Voice Satellite or the Raspberry Pi.

Start the subjective comparison in `listening/`. Every text directory contains
one `full-decode.wav` and streaming variants using 5, 10, 15, 20 and 25 codec
frames per emitted chunk. Files are deliberately named because the comparison
is between chunk sizes, not providers.

`summary.json` contains every raw run, `aggregate.json` contains three-warm-run
aggregates, and each run directory contains timestamped `events.jsonl`, metrics,
the selected assembled WAV and individual chunk WAV files.
