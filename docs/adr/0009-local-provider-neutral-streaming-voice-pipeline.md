# ADR 0009: Local provider-neutral streaming voice pipeline

## Status

Accepted on 2026-08-09. This ADR supersedes the speech-provider selection and
batch processing parts of ADR 0008. ADR 0008 continues to govern satellite
identity, authentication, owner scope, session ownership and Core-authoritative
action execution.

## Context

The first working Raspberry Pi dialogue path proves wake detection, bounded
capture, local STT, assistant routing, local TTS and playback through the
Creative Pebbles. Its sequential request model waits for a complete recording,
transcript, language-model response and WAV file. Measured end-of-speech to
first-audio latency is consequently too high for natural conversation.

The selected Velora reference voice is `velora-f`, originally created with
Qwen3-TTS VoiceDesign and later cloned by Qwen and Chatterbox. Voice identity is
a product asset and must not belong to one runtime provider. The current
Chatterbox path remains useful as a working fallback, but it returns complete
audio and must not define the future dialogue protocol.

Cloud realtime voice providers may eventually be optional adapters. Requiring
one would conflict with Kyrion's local-first and offline-friendly foundations.

## Decision

Velora will use a fully local, provider-neutral streaming pipeline as its target
architecture:

```text
satellite PCM frames
    -> local VAD
    -> streaming STT
    -> Core-owned dialogue turn
    -> streaming LLM text
    -> phrase/sentence boundary policy
    -> streaming TTS
    -> PCM audio frames
    -> satellite jitter/playback buffer
```

The first hardware profile keeps frame-based VAD and STT on CPU. Faster-Whisper
remains CPU `int8` until a measured alternative is selected. The conversational
LLM and TTS runtime may remain warm on the GPU only when measured steady-state
and peak memory leave safe headroom on the RTX 2070 8 GB. Models must not be
swapped into GPU memory for every turn.

Core owns authenticated voice sessions, turn identifiers, cancellation state,
conversation context, audit correlation and all validation or execution of
proposed actions. AI providers do not authenticate satellites or gain command
authority. A long-lived transport may carry audio and control events, but it
must preserve these Core boundaries.

STT, LLM and TTS are expressed through streaming provider contracts. Each
provider reports capabilities instead of having the dialogue controller infer
them from a provider name. Capabilities include at least:

- incremental input support;
- incremental output support;
- voice cloning support where applicable;
- cancellation support;
- accepted audio formats and sample rates;
- minimum text granularity and buffering requirements.

Every event is scoped by session and turn ID. Cancellation is part of the
initial contract even before full barge-in is enabled. When user speech begins
while Velora is speaking, a later barge-in slice can cancel generation, discard
queued chunks for the old turn, stop satellite playback and start a new turn
without redesigning the protocol.

`velora-f` is the qualitative reference voice and is stored as a
provider-independent voice profile with immutable reference audio, transcript,
checksum, provenance and preferred sampling metadata. Qwen- and
Chatterbox-specific conditioning are derived artifacts stored separately; no
provider may overwrite the canonical reference.

Chatterbox remains the legacy fallback until a local streaming TTS provider
passes reproducible latency, quality, memory, stability and licence gates. Qwen
is a candidate adapter, not a dependency of the dialogue controller.

No cloud provider is required. Future local or cloud adapters may implement the
same contracts, but optional cloud behaviour must be explicit and must not
alter the local protocol or Core authority boundary.

## Consequences

- Latency is evaluated primarily as end-of-speech to first playable PCM, not
  only total request duration.
- Provider claims distinguish true model/audio streaming, incremental
  generation and sentence/phrase chunking.
- The protocol carries cancellation and sequence information before barge-in is
  productised.
- Keeping multiple GPU models warm requires a measured deployment profile and
  explicit memory budget.
- The existing batch Chatterbox route remains available during migration and
  can be removed only after the streaming path is stable.
- Provider-specific optimisations or forks require their own maintenance and
  regression-test assessment.

## Deferred work

This decision does not itself implement continuous Pi audio transport,
streaming STT, a new dialogue controller, audio buffering or barge-in. Those
remain staged vertical slices after the TTS runtime benchmark and selection.
