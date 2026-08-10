# XTTS-v2 Experimental MVP Provider

Date: 2026-08-11

## Decision

XTTS-v2 is integrated as an explicitly selected experimental TTS candidate,
not as the default provider. `http_batch` and the existing Chatterbox runtime
remain unchanged and are the stable batch path and automatic fallback.

This is an MVP integration go for physical Raspberry Pi and Pebble listening,
not a default-provider go. Default selection remains blocked on reliable short
output correctness and a stable public XTTS termination mechanism.

## Boundary

Core and its speech contracts are unchanged. The AI service's existing WAV
endpoint is also unchanged. Internally, the XTTS adapter consumes the existing
provider-neutral PCM streaming contract and holds the complete candidate WAV
until validation succeeds. This transactional boundary means a provider crash,
timeout, invalid event stream or suspiciously long result can fall back to
Chatterbox without leaking partial or duplicate audio to playback.

The trade-off is explicit: this slice validates real incremental XTTS
generation and permits physical end-to-end listening, but does not yet stream
PCM across the Core/Pi transport. That transport should not be enabled until
short-output termination is solved.

## Runtime and safety choices

- XTTS requires both `KYRION_TTS_PROVIDER=xtts` and
  `KYRION_XTTS_EXPERIMENTAL_ENABLED=true`.
- The runtime keeps the measured 20-token chunk size and the benchmark decoding
  parameters.
- No Faster-Whisper live guard is present in the production path.
- The Velora-F reference remains checksum-pinned and immutable.
- A generous duration bound uses text word count but never filters vocabulary,
  language, names or mixed DE/EN terms.
- `model.gpt.max_gen_mel_tokens` is touched only in the isolated XTTS runtime.
  It is documented in code and configuration as an unstable MVP workaround,
  restored after every generation and absent from all public contracts.

## Observability

Successful XTTS requests log provider ID, TTFA, generation RTF, simulated
320-millisecond playback-buffer underruns, audio duration, text character count
and an empty fallback reason. Rejected requests log the stable fallback
provider and a bounded reason (`suspicious_duration`, `timeout` or
`provider_failure`). Text and audio content are not logged.

## Remaining gate

The adapter and fallback behavior are unit tested with synthetic streams. A
real GPU runtime and the physical Raspberry Pi/Pebble path still require owner
verification. XTTS must remain opt-in until repeated short-DE outputs terminate
correctly without the private cap, or XTTS exposes an adequate stable public
termination control.
