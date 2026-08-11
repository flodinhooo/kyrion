# Deterministic voice-response architecture slice

Date: 2026-08-11

## Decision

The provider-neutral Fixed/Template/Dynamic response architecture is accepted
and its first vertical slice is implemented. This follows the reproducible
negative XTTS v2 dynamic Short-output decision. No XTTS EOS, runtime or provider
adapter code was changed.

[ADR 0010](../adr/0010-core-owned-typed-voice-response-plans.md) records the
durable Core-to-AI boundary.

## Implemented behaviour

Core now creates typed plans from semantic outcome provenance:

- `session.greeting`, `session.farewell` and `dialogue.acknowledged` resolve to
  deterministic fixed plans with German and English catalog variants;
- Core-confirmed `command.succeeded` and `command.failed` outcomes resolve to
  localized templates with a validated `entityName` slot;
- ordinary LLM output resolves explicitly to a dynamic plan;
- the live Voice turn uses a fixed plan for an explicit farewell and a dynamic
  plan for ordinary dialogue;
- deterministic variant selection is derived from owner, session, turn,
  response key and catalog revision;
- LLM catalog proposals are restricted to acknowledgement in this slice;
  command-success proposals and proposals containing trusted slots are
  rejected.

The AI service exposes a typed response-resolution endpoint:

- fixed plans look up checksum-pinned WAV files in a versioned manifest;
- template plans use a content-addressed complete-utterance WAV cache;
- catalog, voice-profile and synthesis revisions participate in cache identity;
- template caches use a stable hashed owner scope so personalized names and
  aliases are not reused across owners;
- dynamic plans use the existing normal provider-neutral synthesis path;
- missing fixed assets and template cache misses use the injected existing
  stable batch fallback and are explicitly reported as fallback reasons; they
  do not route through an explicitly selected experimental XTTS runtime.

The cache defaults to the operating-system temporary directory and can be
placed in persistent local data with `KYRION_VOICE_RESPONSE_CACHE_DIR`.
Generated cache audio is not committed.

## Deliberately incomplete

- No fixed-response audio is approved yet. The manifest contains only the
  complete pending-asset inventory; it contains no invented or generated
  production WAVs.
- Session greeting remains the Satellite's existing optional local greeting
  file. The resolver exists, but the session-open protocol was not expanded in
  this slice.
- Dialogue acknowledgement is available to the registry and proposal
  validator, but the current free-form chat stream does not yet emit structured
  response proposals.
- Command success and failure resolvers are implemented and tested, but the
  current Voice controller still does not add a second device-command
  orchestration path.
- Template cache misses still use the existing stable batch fallback behind an
  injectable boundary. No dedicated Short-TTS provider was selected or implied.
- Cache retention, quotas and cleanup policy remain operational follow-up work.

These limits preserve existing Voice, command-authority and Satellite
boundaries while proving the new contract.

## Required reviewed fixed assets

Record, listen-review and approve these Velora variants in both German and
English:

| Response | Variants per locale |
| --- | --- |
| `session.greeting` | `neutral-01`, `warm-01` |
| `session.farewell` | `neutral-01`, `warm-01` |
| `dialogue.acknowledged` | `neutral-01`, `neutral-02` |

Each accepted WAV must be mono RIFF/WAV, use the agreed playback sample rate,
identify the immutable Velora voice-profile checksum, and receive a SHA-256
entry in `services/ai/voice-responses/manifest.json`. Recordings require human
review for exact wording, clean ending, pronunciation, prosody, loudness and
silence. The pending entry is removed only when its reviewed asset is added.

## Separate Category-B Short-TTS benchmark

After the product boundary and reviewed fixed assets are accepted, evaluate a
Short-TTS candidate as a new adapter behind the existing `NormalTtsFallback`
boundary. Do not alter Core routing or infer category from text length.

Use cache misses from the registered German and English command templates plus
names, rooms, numbers and mixed DE/EN terms. Compare candidates on:

- exact semantic completion and zero fantasy continuation;
- Velora voice similarity and stable identity;
- names, numbers, `Velora`, `Gamingraum` and mixed `desk lamp` pronunciation;
- warm first-playable latency and real-time factor;
- deterministic repeatability, cancellation and PCM contract compliance;
- CPU/GPU memory, concurrency and local deployment cost;
- licence and redistribution constraints.

A candidate must first pass the isolated corpus. Only then should the AI
composition root inject it for template cache misses. Category A continues to
use reviewed assets and Category C continues to use normal provider-neutral
TTS.

## Verification

- AI Ruff: passed;
- AI pytest: 91 passed;
- Core response-plan tests: 8 passed;
- complete Core test run: 55 passed, one unrelated Testcontainers integration
  test could not start because Docker was unavailable;
- Core compilation as part of the test run: passed.
